""" Simple standard nodes. """
import itertools
import os
import posixpath

import six

from .base import Node
from pike.items import FileMeta, FileDataBlob
from pike.util import recursive_glob, resource_spec, md5stream


class GlobNode(Node):

    """
    Source node that creates a stream of files via glob matching.

    The parameters are the same as :meth:`~pike.util.recursive_glob`

    """

    name = 'glob_source'

    def __init__(self, root, patterns, prefix=''):
        super(GlobNode, self).__init__()
        self.root = resource_spec(root)
        self.patterns = patterns
        self.prefix = prefix

    def process(self):
        filenames = recursive_glob(self.root, self.patterns, self.prefix)
        return [FileMeta(filename, self.root) for filename in filenames]


class MergeNode(Node):

    """
    Merge all unnamed edges into a single stream.

    Example
    -------
    ::

        with Graph('g'):
            m = pike.merge()
            pike.glob('lib', '*.js') | m
            pike.glob('app', '*.js') | m

    """
    name = 'merge'

    def process(self, *args):
        return itertools.chain(*args)


class ConcatNode(Node):

    """
    Concatenate the contents of all the files together into one.

    Parameters
    ----------
    filename : str
        The name of the file to generate
    joinstr : str, optional
        The character to use for joining the files together (default '\\n')

    """
    name = 'concat'

    def __init__(self, filename, joinstr='\n'):
        super(ConcatNode, self).__init__()
        self.filename = filename
        self.joinstr = joinstr

    def process(self, stream):
        datas = []
        ball = FileMeta(self.filename, os.curdir)
        for item in stream:
            datas.append(item.data.read())
        ball.data = FileDataBlob(self.joinstr.join(datas))
        return [ball]


class UrlNode(Node):

    """
    Generate a url for each file.

    Parameters
    ----------
    prefix : str, optional
        Add this prefix to each of the urls
    bust : bool, optional
        If True, add a cache-busting query string (default True)

    Notes
    -----
    Using a cache-busting query string may cause your browser to be unable to
    use source maps.

    """
    name = 'url'

    def __init__(self, prefix='', bust=False):
        super(UrlNode, self).__init__()
        self.prefix = prefix
        self.bust = bust

    def process_one(self, item):
        item.url = posixpath.join('', self.prefix, item.filename)
        if self.bust:
            with item.data.open() as stream:
                item.url += '?' + md5stream(stream)[:8]
        return item


class SplitExtNode(Node):

    """
    Split a single stream of files into named outputs by file extension.

    Parameters
    ----------
    default : str, optional
        The name of the file extension to use as the 'default' output. By
        default there will be no 'default' output; all outbound edges must be
        named.

    Examples
    --------
    ::

        with pike.Graph('g') as graph:
            p = pike.glob('static', '*')
            p |= pike.splitext()
            p * '.js' | pike.concat() | graph.sink
            p * '.css' | pike.concat() | graph.sink

    """
    name = 'splitext'
    outputs = ('*')

    def __init__(self, default=None):
        super(SplitExtNode, self).__init__(self)
        self.default = default

    def process(self, stream):
        ret = {}
        for item in stream:
            ext = os.path.splitext(item.filename)[1]
            ret.setdefault(ext, []).append(item)
        if self.default is not None:
            ret['default'] = ret[self.default]
            del ret[self.default]
        return ret


class WriteNode(Node):

    """
    Write file data to an output file.

    Parameters
    ----------
    base_dir : str, optional
        The base directory to write into (default '.')
    debug : bool, optional
        If True, only print filenames, don't actually write (default False)

    """

    name = 'write'

    def __init__(self, base_dir=os.curdir, debug=False):
        super(WriteNode, self).__init__()
        self.base_dir = resource_spec(base_dir)
        if not os.path.isabs(self.base_dir):
            raise ValueError("Write directory must be an absolute path")
        self.debug = debug

    def process_one(self, item):
        item.path = self.base_dir
        if self.debug:
            six.print_("Output file: %s" % item.fullpath)
        else:
            item.data.as_file(item.fullpath)
        return item


class FilterNode(Node):

    """
    Quick way to filter files out of a stream.

    Parameters
    ----------
    condition : callable
        Function that returns True for files to keep
    name : str, optional
        You may uniquely name this operation (default 'filter')

    """

    def __init__(self, condition, name='filter'):
        super(FilterNode, self).__init__(name)
        self.condition = condition

    def process(self, stream):
        return filter(self.condition, stream)


class MapNode(Node):

    """
    Quick way to run a function on the files.

    Parameters
    ----------
    op : callable
        Function that returns the processed item
    name : str, optional
        You may uniquely name this operation (default 'map')

    """

    def __init__(self, op, name='map'):
        super(MapNode, self).__init__(name)
        self.op = op

    def process_one(self, item):
        return self.op(item)
