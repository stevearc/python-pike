""" Nodes that read files. """
from .base import Node
from pike.items import FileMeta
from pike.util import recursive_glob, resource_spec


class SourceNode(Node):

    """
    Base class for source nodes.

    Source nodes are nodes that read files from disk and inject them into a
    graph.

    """

    name = 'source'

    def __init__(self, root):
        super(SourceNode, self).__init__()
        self.root = resource_spec(root)

    def process(self):
        return [FileMeta(filename, self.root) for filename in self.files()]

    def files(self):
        """
        Return a list of all filenames for this source node (relative to
        self.root)

        """
        raise NotImplementedError


class GlobNode(SourceNode):

    """
    Source node that creates a stream of files via glob matching.

    The parameters are the same as :meth:`~pike.util.recursive_glob`

    """

    name = 'glob_source'

    def __init__(self, root, patterns, prefix=''):
        super(GlobNode, self).__init__(root)
        self.patterns = patterns
        self.prefix = prefix

    def files(self):
        return recursive_glob(self.root, self.patterns, self.prefix)
