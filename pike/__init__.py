""" Pike """
from .graph import Graph
from .nodes import (Node, Edge, AliasNode, NoopNode, SourceNode, GlobNode,
                    CoffeeNode, LessNode, MergeNode, UrlNode, SplitExtNode,
                    WriteNode, ConcatNode, FilterNode, MapNode, XargsNode,
                    ChangeListenerNode, CacheNode)
from .env import Environment, watch_graph
from .exceptions import ValidationError, StopProcessing


def includeme(config):
    """ Redirect to the pyramid extension's includeme """
    from .server import pyramid_extension
    pyramid_extension.includeme(config)


def flaskme(app):
    """ Redirect to the flask extension's configure """
    from .server import flask_extension
    flask_extension.configure(app)


def _make_change_listener():
    """ Create a macro that will watch a node for changes """
    with Graph('change_listener') as graph:
        wrapped = AliasNode()
        ChangeListenerNode() | wrapped * '*' | '*' * CacheNode()
    return graph.macro(pipe=wrapped)


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
alias = AliasNode
xargs = XargsNode
watch = _make_change_listener()
