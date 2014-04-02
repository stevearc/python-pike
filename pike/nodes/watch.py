""" Nodes for watching files for changes. """
import os

import copy
import six

from .base import Node
from pike.exceptions import StopProcessing
from pike.items import FileDataBlob
from pike.sqlitedict import SqliteDict
from pike.util import md5stream
try:
    from collections import OrderedDict
except ImportError:  # pragma: no cover
    from ordereddict import OrderedDict


class ChangeListenerNode(Node):

    """
    Filter source files and detect changes.

    It has two outputs, the default and 'all'. The default output contains only
    the changed files. The 'all' edge will contain all files from the source.

    Parameters
    ----------
    stop : bool, optional
        If True, stop processing the graph if no changes are detected at this
        node (default True)
    cache : str, optional
        Name of the file to cache data in. By default will cache data in
        memory.
    key : str, optional
        Table name to use inside the ``cache`` file. Must be present if
        ``cache`` is non-None.
    fingerprint: str or callable
        Function that takes a file and returns a fingerprint. May also be the
        strings 'md5' or 'mtime', which will md5sum the file or check the
        modification time respectively. (default 'md5')

    """
    name = 'change_listener'
    outputs = ('default', 'all')

    def __init__(self, stop=True, cache=None, key=None, fingerprint='md5'):
        super(ChangeListenerNode, self).__init__()
        self.stop = stop
        if cache is None:
            self.checksums = {}
        elif key is None:
            raise ValueError("If cache is provided, must provide a key")
        else:
            self.checksums = SqliteDict(cache, key, autocommit=False,
                                        synchronous=0)
        if fingerprint == 'md5':
            self.fingerprint = self._md5
        elif fingerprint == 'mtime':
            self.fingerprint = self._mtime
        else:
            self.fingerprint = fingerprint

    def _md5(self, item):
        """ md5sum a file """
        with item.data.open() as filestream:
            return md5stream(filestream)

    def _mtime(self, item):
        """ Get the modification time of a file """
        return os.path.getmtime(item.fullpath)

    def process(self, stream):
        changed = []
        all_items = []
        for item in stream:
            fingerprint = self.fingerprint(item)
            if fingerprint != self.checksums.get(item.fullpath):
                self.checksums[item.fullpath] = fingerprint
                changed.append(item)
            all_items.append(item)
        if not changed and self.stop:
            raise StopProcessing
        if isinstance(self.checksums, SqliteDict):
            self.checksums.commit()
        return {
            'default': changed,
            'all': all_items,
        }


class ChangeEnforcerNode(Node):

    """
    Listen for inputs from :class:`~.ChangeListenerNode` and raise
    :class:`~pike.StopProcessing` if none of the listeners have detected any
    changes.

    """

    name = 'change_enforcer'
    outputs = ('*')

    def __init__(self):
        super(ChangeEnforcerNode, self).__init__()

    def process(self, **kwargs):
        ret = {}
        has_changes = False
        for name, stream in six.iteritems(kwargs):
            if name.endswith('_all'):
                continue
            if stream:
                has_changes = True
            if name + '_all' in kwargs:
                ret[name] = kwargs[name + '_all']
            else:
                ret[name] = stream
        if not has_changes:
            raise StopProcessing
        return ret


class CacheNode(Node):

    """
    Cache the values that pass through this node.

    This is useful if you have a :class:`~.ChangeListenerNode` and only wish to
    process the updated files. You can put a CacheNode after the processing,
    and all of the results will be passed on.

    ..note::
        The CacheNode handles new and changed files, but if you remove a file
        it will still appear in the output of the CacheNode.

    Parameters
    ----------
    cache : str, optional
        Name of the file to cache data in. By default will cache data in
        memory.
    key : str, optional
        Table name to use inside the ``cache`` file. Must be present if
        ``cache`` is non-None.

    """

    name = 'cache'
    outputs = ('*')

    def __init__(self, cache=None, key=None):
        super(CacheNode, self).__init__()
        if cache is None:
            self.cache = {}
        elif key is None:
            raise ValueError("If cache is provided, must provide a key")
        else:
            self.cache = SqliteDict(cache, key, autocommit=False,
                                    synchronous=0)

    def process(self, default=None, **kwargs):
        if default is not None:
            kwargs['default'] = default
        ret = {}
        for stream, items in six.iteritems(kwargs):
            stream_cache = self.cache.setdefault(stream, OrderedDict())
            for item in items:
                stream_cache[item.fullpath] = item
            ret[stream] = []
            for item in six.itervalues(stream_cache):
                clone = copy.copy(item)
                clone.data = FileDataBlob(clone.data.read())
                ret[stream].append(clone)
            if isinstance(self.cache, SqliteDict):
                self.cache[stream] = stream_cache
                self.cache.commit()
        return ret
