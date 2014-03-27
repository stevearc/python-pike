""" Classes for wrapping items and file data """
import os

import contextlib
import shutil
from six import StringIO

from .util import atomic_open


class IFileData(object):

    """
    Abstract interface for accessing file data.

    This provides a common interface to access file data, regardless of the
    source.

    """

    def open(self):
        """
        Get the data as a stream.

        Returns
        -------
        stream : stream
            Data stream as a context manager. Should be used in ``with``
            statemnts.

        """
        raise NotImplementedError

    def read(self):
        """
        Returns all file data as a string

        Returns
        -------
        data : str

        """
        raise NotImplementedError

    def as_file(self, filename):
        """
        Put the file data into a file on disk.

        Parameters
        ----------
        filename : str
            The path of the file to write

        """
        raise NotImplementedError


class FileDataStream(IFileData):

    """ Common data interface for a stream. """

    native = 'stream'

    def __init__(self, stream):
        self.stream = stream

    @contextlib.contextmanager
    def open(self):
        try:
            yield self.stream
        finally:
            self.stream.seek(0)

    def read(self):
        try:
            return self.stream.read()
        finally:
            self.stream.seek(0)

    def as_file(self, filename):
        with atomic_open(filename, 'w') as ofile:
            for chunk in iter(lambda: self.stream.read(16 * 1024), ''):
                ofile.write(chunk)
        self.stream.seek(0)


class FileDataFile(IFileData):

    """ Common data interface for a file on disk """
    native = 'file'

    def __init__(self, filename):
        self.filename = filename

    def open(self):
        return open(self.filename, 'r')

    def read(self):
        with self.open() as ifile:
            return ifile.read()

    def as_file(self, filename):
        dirname = os.path.dirname(filename)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        shutil.copy(self.filename, filename)


class FileDataBlob(IFileData):

    """ Common data interface for a file in memory """
    native = 'blob'

    def __init__(self, data):
        self.data = data

    @contextlib.contextmanager
    def open(self):
        stream = StringIO(self.data)
        try:
            yield stream
        finally:
            stream.close()

    def read(self):
        return self.data

    def as_file(self, filename):
        with atomic_open(filename, 'w') as ofile:
            ofile.write(self.data)


class FileMeta(object):

    """
    Wrapper for file metadata

    Parameters
    ----------
    filename : str
        Relative path to the file
    path : str
        Root path prefix to the current directory
    **kwargs : dict
        Additional keys and values to set on the object

    Attributes
    ----------
    data : :class:`~.IFileData`

    """

    def __init__(self, filename, path, data=None, **kwargs):
        self.filename = filename
        self.path = path
        self.data = data or FileDataFile(os.path.join(path, filename))
        self.__dict__.update(kwargs)

    @property
    def fullpath(self):
        """ Generate the full path to the file """
        return os.path.join(self.path, self.filename)

    def setext(self, ext):
        """ Set the extension on the filename """
        self.filename = os.path.splitext(self.filename)[0] + ext

    def __repr__(self):
        return 'File(%s)' % self.filename

    def __eq__(self, other):
        return (isinstance(other, FileMeta) and
                self.filename == other.filename and
                self.path == other.path)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.filename) + hash(self.path)
