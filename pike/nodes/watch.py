""" Nodes for watching files for changes. """
import six
import copy
from pike.exceptions import StopProcessing
from collections import defaultdict
try:
    from collections import OrderedDict
except ImportError:  # pragma: no cover
    # Python 2.6
    from ordereddict import OrderedDict  # pylint: disable=F0401
from hashlib import md5  # pylint: disable=E0611

from .base import Node
from pike.items import FileDataBlob
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

    """ TODO: listen on all inputs """

    name = 'change_listener'
    outputs = ('default', 'all')

    def __init__(self, stop=True):
        super(ChangeListenerNode, self).__init__()
        self.checksums = {}
        self.stop = stop

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
        return {
            'default': changed,
            'all': all_items,
        }

    def __copy__(self):
        clone = super(ChangeListenerNode, self).__copy__()
        clone.checksums = {}
        return clone


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

    """ TODO: support durable storage """

    name = 'cache'
    outputs = ('*')

    def __init__(self):
        super(CacheNode, self).__init__()
        self.cache = defaultdict(OrderedDict)

    def process(self, default=None, **kwargs):
        if default is not None:
            kwargs['default'] = default
        ret = {}
        for stream, items in six.iteritems(kwargs):
            for item in items:
                self.cache[stream][item.fullpath] = item
            ret[stream] = []
            for item in six.itervalues(self.cache[stream]):
                clone = copy.copy(item)
                clone.data = FileDataBlob(clone.data.read())
                ret[stream].append(clone)
        return ret

    def __copy__(self):
        clone = super(CacheNode, self).__copy__()
        clone.cache = defaultdict(OrderedDict)
        return clone
