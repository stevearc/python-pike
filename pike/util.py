""" Utilities for pike. """
import fnmatch
import locale
import os
import time

import contextlib
import functools
import logging
import shlex
import shutil
import six
import subprocess
import tempfile
from hashlib import md5  # pylint: disable=E0611
from uuid import uuid1


LOG = logging.getLogger(__name__)


class memoize(object):  # pylint: disable=C0103

    """
    Memoize a function/method call.

    Because of the way the caching works, this should only decorate functions
    that only accept immutable types as arguments.

    Examples
    --------
    ::

        @memoize(timeout=5)
        def fetch_from_db(self, key):
            return some_long_running_process(key)

    """
    _caches = {}
    _expires = {}

    def __init__(self, timeout=1):
        self.timeout = timeout

    @classmethod
    def clear(cls):
        """ Clear all cached results for all memoized decorators """
        cls._caches.clear()
        cls._expires.clear()

    def __call__(self, func):
        cache = self._caches[func] = {}
        expires = self._expires[func] = {}

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """ Wrap the decorated function to check cache first. """
            key = (args, tuple(sorted(six.iteritems(kwargs))))
            if time.time() <= expires.get(key, 0):
                return cache[key]
            else:
                ret = func(*args, **kwargs)
                cache[key] = ret
                expires[key] = time.time() + self.timeout
                return ret

        return wrapper


@contextlib.contextmanager
def tempd():
    """ Context manager for creating a temporary working directory. """
    dirname = tempfile.mkdtemp()
    try:
        yield dirname
    finally:
        shutil.rmtree(dirname)


def run_cmd(cmd, stdin=None, cwd=None):
    """
    Shortcut for running a shell command.

    Parameters
    ----------
    cmd : list or str
        The command to be run in the shell
    stdin : stream, optional
        Optional stream to feed to the proc's stdin
    cwd : str, optional
        Before running the command, cd into this directory

    Returns
    -------
    output : str
        The stdout of the process

    Raises
    ------
    exc : :class:`~subprocess.CalledProcessError`
        If the process return code is not 0

    """
    if isinstance(cmd, six.string_types):
        cmd = shlex.split(cmd)

    encoding = locale.getdefaultlocale()[1] or 'utf-8'
    if stdin is not None:
        if not isinstance(stdin, six.binary_type):
            stdin = stdin.encode(encoding)
        inpipe = subprocess.PIPE
    else:
        inpipe = None
    proc = subprocess.Popen(cmd, stdin=inpipe, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, cwd=cwd)
    stdout, stderr = proc.communicate(stdin)
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd,
                                            stdout + stderr)
    elif stderr:
        LOG.warn("%s", stderr)
    return stdout


@contextlib.contextmanager
def atomic_open(filename, mode):
    """ Open a tmpfile and rename it to dest file after """
    dirname = os.path.dirname(filename)
    basename = os.path.basename(filename)
    if not os.path.exists(dirname):
        try:
            os.makedirs(dirname)
        except os.error:
            # can happen if there's a race condition and two threads try to
            # make it at the same time
            pass
    tmp = os.path.join(dirname, '.' + basename + '.tmp.' + uuid1().hex)
    try:
        yield open(tmp, mode)
        os.rename(tmp, filename)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def md5sum(filename):
    """ Calculate the md5 checksum of a file. """
    if not os.path.exists(filename):
        raise os.error("md5(%s) failure, file not found" % filename)
    with open(filename, 'r') as ifile:
        return md5stream(ifile)


def md5stream(stream):
    """ Calulate the md5 checksum of a stream of data. """
    digest = md5()
    for chunk in iter(lambda: stream.read(8192), b''):
        digest.update(chunk)
    return digest.hexdigest()


def resource_spec(path):
    """
    Convert a package resource format to a file path.

    Leaves normal file paths untouched

    Parameters
    ----------
    path : str
        Resource path (format package:dir/subdir)

    Returns
    -------
    path : str
        File path

    """
    if ':' in path:
        package, subpath = path.split(':')
        pkg = __import__(package)
        return os.path.join(os.path.dirname(pkg.__file__), subpath)
    return path


def recursive_glob(root, patterns, prefix=''):
    """
    Recursively search a directory for files matching a pattern.

    Parameters
    ----------
    root : str
        The root directory to search
    patterns : str or list
        This is complicated. See below.
    prefix : str, optional
        Require matched files to be under this subdirectory of ``root``

    Notes
    -----
    In the simplest case, ``recursive_glob`` returns all files whose base name
    matches any glob pattern in the list of patterns. For example:

    .. code-block:: python

        >>> recursive_glob('.', ('*.css', '*.less'))
        ['base.css', 'common/layout.css', 'foo.less']

    The results will be deduplicated; no file will appear twice. The results
    are also ordered. Files that match earlier globs will appear earlier in the
    list:

    .. code-block:: python

        >>> recursive_glob('.', ('base.less', '*.less'))
        ['base.less', 'app.less', 'other.less']

    You can match only files in certain directories by adding a path prefix to
    the pattern. Note that this is applied *on top of* the ``prefix``
    parameter.

    .. code-block:: python

        >>> recursive_glob('.', ('common/*', 'lib/*'))
        ['common/util.js', 'lib/jquery.js']

    You can also *remove* files by placing a ``!`` in front of the pattern

    .. code-block:: python

        >>> recursive_glob('.', '*.js')
        ['app.js', 'app.min.js']
        >>> recursive_glob('.', ('*.js', '!*.min.js'))
        ['app.js']

    Prefixes and bangs can be mixed:

    .. code-block:: python

        >>> recursive_glob('.', '*.js')
        ['app.js', 'debug/annoy.js']
        >>> recursive_glob('.', ('*.js', '!debug/*'))
        ['app.js']

    Instead of passing in a list or tuple of patterns, you can separate them
    with ``:`` like so:

    .. code-block:: python

        >>> recursive_glob('.', '*.css:*.less')
        ['base.css', 'common/layout.css', 'foo.less']

    """

    # Make sure prefix is normalized for OS
    base_prefix = os.path.sep.join(prefix.split('/')).strip(os.path.sep)
    if isinstance(patterns, six.string_types):
        patterns = patterns.split(':')
    filenames = set()
    ordered_filenames = []

    for pattern in patterns:
        remove = False
        # If pattern starts with '!', remove elements instead of adding them
        if pattern.startswith('!'):
            pattern = pattern[1:]
            remove = True
        # If pattern contains a path, extract it and append it to the prefix
        if '/' in pattern:
            pieces = pattern.split('/')
            prefix = os.path.join(base_prefix, *pieces[:-1])
            pattern = pieces[-1]
        else:
            prefix = base_prefix

        for base, _, files in os.walk(os.path.join(root, prefix)):
            rel = base[len(root) + 1:]

            for filename in fnmatch.filter(files, pattern):
                fullpath = os.path.join(rel, filename)
                if remove:
                    if fullpath in filenames:
                        filenames.remove(fullpath)
                        ordered_filenames.remove(fullpath)
                elif fullpath not in filenames:
                    filenames.add(fullpath)
                    ordered_filenames.append(fullpath)
    return ordered_filenames
