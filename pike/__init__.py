""" Pike """
from .graph import Graph
from .nodes import (Node, Edge, PlaceholderNode, NoopNode, SourceNode,
                    GlobNode, CoffeeNode, LessNode, MergeNode, UrlNode,
                    SplitExtNode, WriteNode, ConcatNode, FilterNode, MapNode,
                    XargsNode, ChangeListenerNode, CacheNode)
from .env import Environment, watch_graph
from .exceptions import ValidationError, StopProcessing


def includeme(config):
    """ Redirect to the pyramid extension's includeme """
    from .server import pyramid_extension
    pyramid_extension.includeme(config)


def flaskme(app):
    """ Redirect to the flask extension's configure """
    from .server import flask_extension
    return flask_extension.configure(app)


# pylint: disable=C0103
glob = GlobNode
noop = NoopNode
coffee = CoffeeNode
less = LessNode
merge = MergeNode
url = UrlNode
splitext = SplitExtNode
write = WriteNode
concat = ConcatNode
filter = FilterNode
map = MapNode
placeholder = PlaceholderNode
xargs = XargsNode
listen = ChangeListenerNode
cache = CacheNode
