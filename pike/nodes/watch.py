""" Nodes for watching files for changes. """
import copy
import six
from hashlib import md5  # pylint: disable=E0611

from .base import Node
from pike.exceptions import StopProcessing
from pike.items import FileDataBlob
from pike.sqlitedict import SqliteDict
from pike.util import md5stream


class FingerprintNode(Node):

    """
    Process all files passed in and return a single fingerprint

    """
    name = 'fingerprint'

    def process(self, *streams):
        digest = md5()
        for stream in streams:
            for item in stream:
                with item.data.open() as filestream:
                    for chunk in iter(lambda: filestream.read(8192), ''):
                        digest.update(chunk)
        return digest.digest()


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

    """
    name = 'change_listener'
    outputs = ('default', 'all')

    def __init__(self, stop=True, cache=None, key=None):
        super(ChangeListenerNode, self).__init__()
        self.stop = stop
        if cache is None:
            self.checksums = {}
        elif key is None:
            raise ValueError("If cache is provided, must provide a key")
        else:
            self.checksums = SqliteDict(cache, key, autocommit=False,
                                        synchronous=0)

    def process(self, stream):
        changed = []
        all_items = []
        for item in stream:
            with item.data.open() as filestream:
                fingerprint = md5stream(filestream)
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
            for item in items:
                try:
                    self.cache[stream][item.fullpath] = item
                except KeyError:
                    self.cache[stream] = {item.fullpath: item}
            ret[stream] = []
            for item in six.itervalues(self.cache.get(stream, {})):
                clone = copy.copy(item)
                clone.data = FileDataBlob(clone.data.read())
                ret[stream].append(clone)
            if isinstance(self.cache, SqliteDict):
                self.cache[stream] = self.cache[stream]
        if isinstance(self.cache, SqliteDict):
            self.cache.commit()
        return ret
