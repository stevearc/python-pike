""" Base classes for Nodes """
import inspect
from pike.exceptions import ValidationError
import six


def asnode(node):
    """ Convert non-node objects into a Node """
    wrapper = getattr(node, '__wrapper_node__', None)
    if wrapper is None:
        return node
    return wrapper(node)


def run_node(node, args, kwargs):
    """
    Run a node with some inputs.

    Parameters
    ----------
    node : :class:`~.Node`
    args : list
        Positional arguments to pass to the Node
    kwargs : dict
        Keyword arguments to pass to the Node

    Returns
    -------
    ret : dict
        Dictionary of outputs from the node

    """
    try:
        ret = node.process(*args, **kwargs)
    except Exception as e:
        if not hasattr(e, 'node'):
            e.node = node
        raise
    if not isinstance(ret, dict):
        ret = {'default': ret}
    return ret


class FxnArgs(object):

    """
    Representation of arguments that will be passed to a function.

    Used to test validity of node edges.

    Parameters
    ----------
    positional : int
        Number of positional arguments that are being passed in.
    keywords : list
        List of all keyword arguments that are being passed in.

    """

    def __init__(self, positional, keywords):
        self.args = positional
        self.kwargs = set(keywords)

    @classmethod
    def from_edges(cls, edges):
        """ Construct a FxnArgs from a list of edges. """
        args = 0
        kwargs = []
        for edge in edges:
            if edge.input_name is None:
                args += 1
            elif edge.input_name in kwargs:
                raise ValidationError("Duplicate edge input '%s'!" %
                                      edge.input_name)
            else:
                kwargs.append(edge.input_name)
        return cls(args, kwargs)

    def test(self, node, require_inputs=True):
        """
        Test these function arguments on a given Node.

        Parameters
        ----------
        node : :class:`~.Node`
        require_inputs : bool, optional
            If True, require all node positional inputs to be satisfied
            (default True)

        Raises
        ------
        exc : :class:`~pike.ValidationError`
            If the args cannot be passed to the node.

        """
        if '*' in self.kwargs:
            # We cannot effectively inspect '*' edges
            return
        argspec = inspect.getargspec(node.process)
        args = argspec.args[1:]
        positional = len(args) - len(argspec.defaults or [])
        if self.args > positional and not argspec.varargs:
            # Allow a single positional argument to sub in for a single keyword
            # argument if there are no other positional args
            if (len(argspec.defaults or []) == 0 or
                    self.args - positional > 1 or self.args > 1):
                raise ValidationError(
                    "Too many unnamed edge inputs to %s" % node)
        if require_inputs and self.args < positional:
            raise ValidationError("%s requires more edge inputs" % node)
        if not argspec.keywords:
            diff = self.kwargs - set(args)
            if diff:
                raise ValidationError("Unknown input edge '%s' on %s" %
                                      (', '.join(diff), node))


class Edge(object):

    """
    A connection between two Nodes.

    This can also serve as a placeholder for one side of the connection until
    the rest of the data is filled in. Thus, all the arguments are optional
    because they might be filled in later.

    Parameters
    ----------
    n1 : :class:`~.Node`, optional
        Source node for the Edge
    n2 : :class:`~.Node`, optional
        Sink node for the Edge
    output_name : str, optional
        The name of the output side of the Edge. Requires ``n1`` to return this
        value when run. (default 'default')
    input_name : str, optional
        The name of the argument to pass to ``n2``. If None, it will be a
        positional argument.

    """

    def __init__(self, n1=None, n2=None, output_name='default',
                 input_name=None):
        self.n1 = n1
        self.n2 = n2
        self.output_name = output_name
        self.input_name = input_name

    def remove(self):
        """ Remove this edge from the nodes it connects. """
        try:
            if self.n1 is not None:
                self.n1.eout.remove(self)
        except ValueError:
            pass
        try:
            if self.n2 is not None:
                self.n2.ein.remove(self)
        except ValueError:
            pass

    def validate(self):
        """
        Make sure the Edge is fully-formed.

        Raises
        ------
        exc : :class:`~pike.ValidationError`
            If the Edge is missing the source or the sink

        """
        if self.n1 is None or self.n2 is None:
            raise ValidationError("Edge is incomplete: %s" % self)

    def __or__(self, other):
        other = asnode(other)
        if isinstance(other, Node):
            e = self.n1.connect(other, self.output_name, self.input_name)
            return e.n2
        elif isinstance(other, Edge):
            e = self.n1.connect(other.n2, self.output_name, other.input_name)
            return e.n2
        else:
            return NotImplemented

    def __eq__(self, other):
        return (isinstance(other, Edge) and
                self.n1 == other.n1 and
                self.n2 == other.n2 and
                self.output_name == other.output_name and
                self.input_name == other.input_name
                )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        if self.n1 is None or self.n2 is None:
            raise TypeError("'Edge' is unhashable until both nodes are set")
        else:
            return hash(self.n1) + hash(self.n2)

    def __repr__(self):
        n1 = '%s[%s]' % (self.n1, self.output_name)
        n2 = str(self.n2)
        if self.input_name is not None:
            n2 = '[%s]' % self.input_name + n2
        return '%s -> %s' % (n1, n2)


class Node(object):

    """
    Base class for all nodes ever present in a Graph.

    Note that it is IMPORTANT for subclasses to call super().__init__()

    Attributes
    ----------
    name : str
        Used when pretty-printing and debugging
    graph : :class:`~pike.graph.Graph`
        The graph this node belongs to, if any
    outputs : tuple
        Names of all output edges that this node can return. This is used for
        Edge validation. If any output should be considered valid, use '*'.

    """
    name = None
    graph = None
    outputs = ('default')

    def __init__(self, name='unknown'):
        if self.name is None:
            self.name = name
        self.eout = []
        self.ein = []
        from pike import Graph
        Graph.register_node(self)

    @property
    def source(self):
        """ True if this node accepts no inputs and generates output """
        argspec = inspect.getargspec(self.process)
        return (len(self.outputs) > 0 and not argspec.varargs and not
                argspec.keywords and len(argspec.args) == 1)

    @property
    def accepts_input(self):
        """ True if the Node accepts any args or kwargs """
        argspec = inspect.getargspec(self.process)
        return argspec.varargs or argspec.keywords or len(argspec.args) > 1

    def deregister(self):
        """ Deregister a node from its parent graph """
        if self.graph is not None:
            self.graph.remove(self)

    def validate(self, require_inputs=True):
        """
        Perform validation checks to make sure the edges are well-formed.

        Raises
        ------
        exc : :class:`~pike.ValidationError`
            If the node or connected edges are not well-formed

        """
        # Make sure input edges are dangling
        for edge in self.ein:
            edge.validate()

        # Make sure input edges match function signature of self.process()
        args = FxnArgs.from_edges(self.ein)
        args.test(self, require_inputs)

        # Make sure all output edges are supported
        if isinstance(self.outputs, six.string_types):
            outputs = set([self.outputs])
        else:
            outputs = set(self.outputs)

        # Validate output edges
        used_outputs = set()
        for edge in self.eout:
            if edge.output_name in used_outputs:
                raise ValidationError("%s has duplicate output edge '%s'" %
                                      (self, edge.output_name))
            used_outputs.add(edge.output_name)
            if ('*' not in outputs and edge.output_name != '*' and
                    edge.output_name not in outputs):
                raise ValidationError("%s has no output edge %s" %
                                      (self, edge.output_name))
            # Make sure output edges aren't dangling
            edge.validate()
        if '*' in used_outputs and len(used_outputs) > 1:
            raise ValidationError("%s output edge '*' is used; no other "
                                  "output edges allowed" % self)

    def process(self, default):
        """
        Entry point for running a node.

        This may be overridden by subclasses. As you change the method
        signature (adding/removing arguments), the node will accept/reject
        edges with the same name.

        If your node only needs to have a single input and output, and only
        operates on a single item at a time, consider overriding
        :meth:`~.process_one` instead.

        Returns
        -------
        ret : object or dict
            If ret is an object, it will be translated to {'default': ret}.
            This makes it easer to create simple nodes.

        """
        return [self.process_one(item) for item in default]

    def process_one(self, item):
        """
        Your Node subclass may override this instead of :meth:`~.process`.

        The default behavior of Node will accept one input and call
        ``process_one`` on each item in that input.

        """
        raise RuntimeError()

    def connect(self, other, output_name='default', input_name=None):
        """
        Create a connecting edge to another node.

        Parameters
        ----------
        other : :class:`~.Node`
            The sink node to connect to
        output_name : str, optional
            Same as on :class:`~.Edge`
        input_name : str, optional
            Same as on :class:`~.Edge`

        """
        other = asnode(other)
        if output_name == '*' and input_name != '*':
            # n1.connect(n2, '*') is the same as putting n2 inside of an
            # XargsNode
            xargs = XargsNode(other)
            xargs.eout = other.eout
            xargs.ein = other.ein
            other = xargs
            input_name = '*'
        elif input_name == '*' and output_name != '*':
            raise ValidationError("%s cannot use '*' for input edge without "
                                  "'*' as the output edge" % self)

        for edge in self.eout:
            if edge.output_name == output_name:
                raise ValidationError("Cannot double-assign output '%s' on %s"
                                      % (output_name, self))
        if input_name is not None:
            for edge in other.ein:
                if edge.input_name == input_name:
                    raise ValidationError("Cannot double-assign input '%s' "
                                          "on %s" % (output_name, other))
        edge = Edge(self, other, output_name, input_name)
        self.eout.append(edge)
        other.ein.append(edge)
        return edge

    def insert_after(self, node, output_name=None, input_name=None):
        """
        Insert a node after this node, splicing in all edges.

        Parameters
        ----------
        node : :class:`~.Node`
            The node to insert after this one
        output_name : str, optional
            If provided, use this output for ``node`` in place of the output
            used from the current node.
        input_name : str, optional
            If provided, use this input for ``node`` in place of the input
            used for the node that comes after this one.

        """
        multi_edge = (len(self.eout) > 1 or
                      '*' in [e.output_name for e in self.eout])
        if multi_edge and \
                (output_name is not None or input_name is not None):
            raise ValueError("%s has more than one output edge. You cannot "
                             "specify an input_name or output_name" % self)

        if multi_edge:
            for edge in self.eout[:]:
                self.eout.remove(edge)
                self.connect(node, edge.output_name, edge.input_name)
                edge.n2.ein.remove(edge)
                node.connect(edge.n2, edge.output_name, edge.input_name)
        else:
            if len(self.eout) == 1:
                edge = self.eout[0]
                self.eout.remove(edge)
                edge.n2.ein.remove(edge)
            else:
                edge = Edge(n2=NoopNode())

            self.connect(node, edge.output_name, input_name)
            node.connect(edge.n2, output_name or 'default', edge.input_name)

    def __repr__(self):
        return 'Node(%s)' % self.name

    def __mul__(self, output_name):
        if not isinstance(output_name, six.string_types):
            return NotImplemented
        edge = Edge(n1=self, output_name=output_name)
        return edge

    def __rmul__(self, input_name):
        if not isinstance(input_name, six.string_types):
            return NotImplemented
        edge = Edge(n2=self, input_name=input_name)
        return edge

    def __or__(self, other):
        other = asnode(other)
        if isinstance(other, Node):
            e = self.connect(other)
            return e.n2
        elif isinstance(other, Edge):
            # If this edge is accepting an input, we are the input
            # n1 | 'in' * n2
            if other.n1 is None:
                e = self.connect(other.n2, other.output_name, other.input_name)
                return e.n2
            # Otherwise, use the default edge input to the n1 node
            # n1 | n2 * 'out' | n3
            else:
                self.connect(other.n1)
                return other
        else:
            return NotImplemented

    __ior__ = __or__

    def __copy__(self):
        clone = type(self).__new__(type(self))
        clone.__dict__.update(self.__dict__)
        Node.__init__(clone)
        return clone

    def _edge_dot(self, source, indent, style=None):
        """ Create dot file syntax for outbound edges """
        lines = []
        for edge in self.eout:
            if isinstance(edge.n2, LinkNode):
                n2 = edge.n2.subgraph.source
            else:
                n2 = edge.n2
            label = ''
            if edge.output_name != 'default':
                label += edge.output_name
            label += ':'
            if edge.input_name is not None:
                label += edge.input_name
            dot_edge = indent + '%s -> %d' % (id(source), id(n2))

            # apply styling
            if style is not None and edge in style:
                attrs = dict(style[edge])
            else:
                attrs = {}
            if label != ':' and 'label' not in attrs:
                attrs['label'] = '"%s"' % label
            attr_styles = ' '.join(('='.join(t) for t in attrs.items()))
            if attr_styles:
                dot_edge += ' [%s]' % attr_styles

            lines.append(dot_edge + ';')
        return '\n'.join(lines)

    def dot(self, indent='', style=None):
        """ Create dot file syntax for node and outbound edges """
        if style is not None and self in style:
            attrs = style[self]
            attr_styles = ' ' + ' '.join(('='.join(t) for t in attrs.items()))
        else:
            attr_styles = ''
        lines = [
            indent + '%d [label="%s"%s];' % (id(self), self.name, attr_styles),
            self._edge_dot(self, indent, style=style),
        ]
        return '\n'.join(lines)

    def walk_up(self, include_self=False):
        """
        Walk all nodes in the graph from this point upwards.

        Parameters
        ----------
        include_self : bool, optional
            If True, this node will be included in the generator

        Returns
        -------
        nodes : generator

        """
        if include_self:
            yield self
        for edge in self.ein:
            for n in edge.n1.walk_up(True):
                yield n

    def walk_down(self, include_self=False):
        """
        Walk all nodes in the graph from this point downwards.

        Parameters
        ----------
        include_self : bool, optional
            If True, this node will be included in the generator

        Returns
        -------
        nodes : generator

        """
        if include_self:
            yield self
        for edge in self.eout:
            for n in edge.n2.walk_down(True):
                yield n


class LinkNode(Node):

    """ Wrap a graph for insertion into another graph """

    def __init__(self, subgraph):
        super(LinkNode, self).__init__()
        self.name = str(subgraph)
        self.subgraph = subgraph
        if subgraph.sink is not None:
            self.outputs = subgraph.sink.outputs
        else:
            self.outputs = ()

    @property
    def source(self):
        return self.subgraph.source is None

    def process(self, *args, **kwargs):
        return self.subgraph.run(*args, **kwargs)

    def dot(self, indent='', style=None):
        return '\n'.join([
            self.subgraph.dot(indent, style=style),
            self._edge_dot(self.subgraph.sink, indent, style=style),
        ])

    def walk_up(self, include_self=False):
        for n in self.subgraph.sink.walk_up(True):
            yield n

    def walk_down(self, include_self=False):
        for n in self.subgraph.source.walk_down(True):
            yield n


class PlaceholderNode(Node):

    """
    Placeholder node that can be replaced by other nodes at a later time.

    This is used in the creation of :class:`~pike.graph.Macro`s.

    """
    name = 'placeholder'
    outputs = ('*')

    def replace(self, node):
        """ Set the aliased node. """
        node = asnode(node)
        from pike import Graph
        self.deregister()
        node.deregister()
        Graph.register_node(node)
        node.ein = self.ein
        for edge in self.ein:
            edge.n2 = node
        node.eout = self.eout
        for edge in self.eout:
            edge.n1 = node

    def process(self, *args, **kwargs):
        raise RuntimeError("Placeholder nodes should not be called directly! "
                           "Look for information on Macros.")


class NoopNode(Node):

    """ This node mostly just sits there and passes through all inputs. """
    name = 'noop'
    outputs = ('*')

    def process(self, default=None, **kwargs):
        if default is not None:
            kwargs['default'] = default
        return kwargs


class XargsNode(Node):

    """
    Wrap a node and pass all inputs to that node one-at-a-time.

    This is useful if you have a node that only processes a single stream at a
    time but you want it to process many streams.

    Parameters
    ----------
    node : :class:`~.Node`
        The wrapped node

    """

    name = 'xargs'
    outputs = ('*')

    def __init__(self, node):
        super(XargsNode, self).__init__()
        self.node = asnode(node)
        # This node isn't actually in the graph
        self.node.deregister()

    def process(self, default=None, **kwargs):
        ret = {}
        if default is not None:
            kwargs['default'] = default
        for key, val in six.iteritems(kwargs):
            ret[key] = run_node(self.node, [val], {})['default']
        return ret
