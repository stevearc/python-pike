""" Nodes for watching files for changes. """
import copy
from collections import defaultdict, OrderedDict
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

    def __init__(self):
        super(ChangeListenerNode, self).__init__()
        self.checksums = {}

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
        return {
            'default': changed,
            'all': all_items,
        }


class CacheNode(Node):

    """ TODO: support durable storage """

    name = 'cache'
    outputs = ('*')

    def __init__(self):
        super(CacheNode, self).__init__()
        self.cache = defaultdict(OrderedDict)

    def process(self, default=None, **kwargs):
        kwargs['default'] = default
        ret = {}
        for stream, items in kwargs.iteritems():
            for item in items:
                self.cache[stream][item.fullpath] = item
            ret[stream] = []
            for item in self.cache[stream].itervalues():
                clone = copy.copy(item)
                clone.data = FileDataBlob(clone.data.read())
                ret[stream].append(clone)
        return ret

    def __copy__(self):
        clone = super(CacheNode, self).__copy__()
        clone.cache = OrderedDict()
        return clone
