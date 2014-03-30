""" Core classes for the graph architecture. """
import os

import copy
import logging
import six
import subprocess
import threading

from .exceptions import ValidationError
from .nodes import NoopNode, run_node, LinkNode, Edge, SourceNode
from .util import tempd


LOG = logging.getLogger(__name__)

VIEW_COMMANDS = {
    'png': ['open', 'eog', 'gthumb'],
    'pdf': ['open', 'evince'],
}


def init_topo_sort(nodes):
    """
    Get the source nodes and inbound edges for a set of nodes.

    Parameters
    ----------
    nodes : list
        List of nodes

    Returns
    -------
    source : list
        List of source nodes
    edges : dict
        Dictionary mapping nodes to a set of their inbound edges

    """
    found = set()
    source = set()
    edges = {}
    queue = list(nodes)
    while queue:
        node = queue.pop()
        if node not in found:
            found.add(node)
            if not node.ein:
                source.add(node)
            for edge in node.eout:
                edges.setdefault(edge.n2, set()).add(edge)
                queue.append(edge.n2)
    return source, edges


def topo_sort(inputs):
    """ Sort DAG nodes topographically. """

    output = []
    queue, edges = init_topo_sort(inputs)
    while queue:
        node = queue.pop()
        output.append(node)
        for edge in node.eout:
            edges[edge.n2].remove(edge)
            if len(edges[edge.n2]) == 0:
                del edges[edge.n2]
                queue.add(edge.n2)
    if edges:
        raise ValidationError("Graph has at least one cycle!")
    else:
        return output


def ret_to_args(ret):
    """ Convert a node return value to args and kwargs """
    args = []
    kwargs = {}
    for key, val in six.iteritems(ret):
        if key == 'default':
            args.append(val)
        else:
            kwargs[key] = val
    return args, kwargs


class Macro(object):

    """
    A wrapper around a graph that can create parameterized copies of it.

    Parameters
    ----------
    graph : :class:`~.Graph`
    kwargs : dict
        Mapping of argument name to the index of the node it replaces in the
        graph.

    """

    def __init__(self, graph, kwargs):
        self.graph = graph
        self.kwargs = kwargs

    def __call__(self, *args, **kwargs):
        if len(args) > 0:
            if len(kwargs) > 0 or len(self.kwargs) > 1:
                raise TypeError("%s can only be called with positional "
                                "arguments if it takes a single argument" %
                                self)
            else:
                k = tuple(self.kwargs.keys())[0]
                kwargs[k] = args[0]
        clone = copy.deepcopy(self.graph)
        if set(self.kwargs) != set(kwargs):
            raise TypeError("%s must be called with these arguments: %s" %
                            (self, ', '.join(self.kwargs)))
        for name, index in six.iteritems(self.kwargs):
            clone[index].set_node(kwargs[name])
        return clone

    def __repr__(self):
        return "Macro[%s](%s)" % (self.graph.name, ', '.join(self.kwargs))

BAD_EDGE = ValidationError(
    "Bad graph edge! This can only happen if there is a bug in the "
    "Node.connect() call. Please file a bug. sorry, bro :(")


class Graph(object):

    """
    A Directed Acyclic Graph of Nodes.

    Parameters
    ----------
    name : str
        The name of the graph (used for pretty-printing and debugging)

    """
    graph_context = threading.local()

    def __init__(self, name):
        self.name = name
        self.nodes = []
        self._finalized = False
        self.source = None
        self.sink = None

    def __repr__(self):
        return 'Graph(%s)' % self.name

    def __enter__(self):
        if getattr(self.graph_context, 'instance', None) is not None:
            raise RuntimeError(
                "Cannot enter two graph contexts at the same time")
        self._finalized = False
        if self.source is None:
            self.source = NoopNode()
        if self.sink is None:
            self.sink = NoopNode()
        Graph.graph_context.instance = self
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        Graph.graph_context.instance = None
        if exc_type is None:
            self.finalize()

    @classmethod
    def register_node(cls, node):
        """ If inside a Graph context, add this node to the active graph """
        instance = getattr(cls.graph_context, 'instance', None)
        if instance is not None:
            instance.add(node)

    @classmethod
    def deregister_node(cls, node):
        """ If inside a Graph context, remove this node from the graph """
        instance = getattr(cls.graph_context, 'instance', None)
        if instance is not None:
            instance.remove(node)

    def macro(self, **kwargs):
        """
        Create a macro from this graph.

        Parameters
        ----------
        **kwargs : dict
            Mapping of argument name to the Alias nodes that will be replaced

        Notes
        -----
        To create a macro from a Graph, that Graph must contain one or more
        :class:`~AliasNode`s. You may then call this method to create the
        macro. The ``**kwargs`` arguments should map the name of the macro
        kwarg to the ``AliasNode`` that arg will replace.

        Examples
        --------
        ::

            with Graph('source') as graph:
                a = pike.alias()
            mymacro = graph.macro(files=a)

            source_node = mymacro(files=pike.glob('/tmp', '*'))

        """
        macro_kwargs = dict(((k, self.nodes.index(v)) for k, v in
                             six.iteritems(kwargs)))
        return Macro(self, macro_kwargs)

    def __getitem__(self, key):
        return self.nodes[key]

    def source_nodes(self):
        """ Get all :class:`~pike.SourceNode`s in the graph """
        return [node for node in self.nodes if isinstance(node, SourceNode)]

    def add(self, node):
        """
        Add a node to the graph.

        Raises
        ------
        exc : ValueError
            If the graph has already been finalized

        """
        if self._finalized:
            raise ValueError("Cannot add nodes after Graph has been finalized")
        self.nodes.append(node)

    def remove(self, node):
        """
        Remove a node from the graph.

        Raises
        ------
        exc : ValueError
            If the graph has already been finalized

        """
        if self._finalized:
            raise ValueError("Cannot add nodes after Graph has been finalized")
        try:
            self.nodes.remove(node)
        except ValueError:
            pass

    def finalize(self):
        """ Mark the Graph as immutable and perform validation checks. """

        self._finalized = True

        # Find source if none explicitly used
        if self.source.eout:
            self.nodes.append(self.source)
        else:
            self.source = None
            for node in self.nodes:
                if node.accepts_input and not node.ein:
                    if self.source is None:
                        self.source = node
                    else:
                        raise ValidationError("Ambiguous source node! (%s and "
                                              "%s)" % (self.source, node))

        # Find sink if none explicitly used
        if self.sink.ein:
            self.nodes.append(self.sink)
        else:
            self.sink = None
            for node in self.nodes:
                if len(node.outputs) > 0 and not node.eout:
                    if self.sink is None:
                        self.sink = node
                    else:
                        raise ValidationError("Ambiguous sink node! (%s and "
                                              "%s)" % (self.sink, node))

        self.validate()

        try:
            self.nodes = topo_sort(self.nodes)
        except ValidationError:
            raise ValidationError("%s has at least one cycle!" % self)

    def validate(self):
        """ Validate all nodes in the graph. """
        for node in self.nodes:
            node.validate(node != self.source)

    def run(self, *args, **kwargs):
        """
        Run a graph.

        If the source node of the graph accepts inputs, you may pass in those
        inputs here.

        """
        if not self._finalized:
            raise ValueError("Must call finalize() before running %s" % self)
        inputs = {}
        if (args or kwargs) and self.source is None:
            raise TypeError("This graph takes no inputs")
        else:
            inputs[self.source] = (args, kwargs)

        sink_ret = None
        for node in self.nodes:
            args, kwargs = inputs.get(node, ((), {}))
            ret = run_node(node, args, kwargs)
            if node == self.sink:
                sink_ret = ret
            for edge in node.eout:
                args, kwargs = inputs.setdefault(edge.n2, ([], {}))
                if edge.output_name == '*':
                    if edge.input_name == '*':
                        a, k = ret_to_args(ret)
                        args.extend(a)
                        kwargs.update(k)
                    else:
                        raise BAD_EDGE
                elif edge.input_name is None:
                    args.append(ret[edge.output_name])
                elif edge.input_name == '*':
                    raise BAD_EDGE
                else:
                    kwargs[edge.input_name] = ret[edge.output_name]
        return sink_ret

    def connect(self, *args, **kwargs):
        """ Same operation as :meth:`~pike.Node.connect` """
        link = LinkNode(self)
        return link.connect(*args, **kwargs)

    def __mul__(self, output_name):
        if not isinstance(output_name, six.string_types):
            return NotImplemented
        link = LinkNode(self)
        edge = Edge(n1=link, output_name=output_name)
        return edge

    def __rmul__(self, input_name):
        if not isinstance(input_name, six.string_types):
            return NotImplemented
        link = LinkNode(self)
        edge = Edge(n2=link, input_name=input_name)
        return edge

    def __or__(self, other):
        return LinkNode(self).__or__(other)

    __ior__ = __or__

    def dot(self, indent=''):
        """
        Create dot syntax to represent this graph

        Parameters
        ----------
        indent : str, optional
            Spaces to prefix the graph with. If more that 0, this will be
            written out as a cluster.

        """
        name = self.name.replace(' ', '_')
        lines = []
        if indent:
            lines.append(indent + 'subgraph cluster_%s {' % name)
            lines.append('  label = "%s";' % self.name)
        else:
            lines.append(indent + 'digraph %s {' % name)
        for node in self.nodes:
            lines.append(node.dot(indent + '  '))
        lines.append('}')
        return ('\n%s' % indent).join(lines)

    def show(self, viewer=None, format='png'):
        """
        Compile and view a graphviz image of the graph.

        Parameters
        ----------
        viewer : str, optional
            The command to use to view the compiled file. By default many
            programs will be attempted until one succeeds.
        format : str, optional
            The graphviz format to compile into (the -T argument). Default
            'png'.

        """
        if viewer is None:
            if format not in VIEW_COMMANDS:
                raise ValueError("Unsupported output format '%s'" % format)
            progs = VIEW_COMMANDS[format]
        else:
            progs = [viewer]
        with tempd() as tmp:
            def run(cmd):
                """ Convenience method for calling subprocess """
                try:
                    return subprocess.call(cmd, cwd=tmp)
                except os.error:
                    return 1

            with open(os.path.join(tmp, 'graph.dot'), 'w') as ofile:
                ofile.write(self.dot())
            code = run(['dot', '-Tpng', '-o', 'graph.png', 'graph.dot'])
            if code != 0:
                raise RuntimeError("Dot command failed! Is graphviz "
                                   "installed?")
            for cmd in progs:
                code = run([cmd, 'graph.png'])
                if code == 0:
                    return
            raise RuntimeError("Could not find program to open graph.png")
