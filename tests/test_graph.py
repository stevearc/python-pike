""" Tests for graph constructs """
import pike
from . import ParrotNode
from pike import Node, Edge, Graph, AliasNode
from pike.graph import ValidationError, topo_sort


try:
    import unittest2 as unittest  # pylint: disable=F0401
except ImportError:
    import unittest


class TestNodes(unittest.TestCase):

    """ Tests for basic node operations """

    def test_create_edge(self):
        """ Connect two nodes with a pipe | """
        n1, n2 = Node('a'), Node('b')
        n1 | n2
        self.assertEqual(n1.eout, [Edge(n1, n2)])
        self.assertEqual(n1.ein, [])
        self.assertEqual(n2.ein, [Edge(n1, n2)])
        self.assertEqual(n2.eout, [])

    def test_create_named_output_edge(self):
        """ Create a named output edge via string multiplication """
        n1, n2 = Node('a'), Node('b')
        result = n1 * 'foo' | n2
        self.assertEqual(result, n2)
        self.assertEqual(n1.eout, [Edge(n1, n2, 'foo')])
        self.assertEqual(n1.ein, [])
        self.assertEqual(n2.ein, [Edge(n1, n2, 'foo')])
        self.assertEqual(n2.eout, [])

    def test_create_named_input_edge(self):
        """ Create a named input edge via string multiplication """
        n1, n2 = Node(), Node()
        result = n1 | 'foo' * n2
        self.assertEqual(result, n2)
        self.assertEqual(n1.eout, [Edge(n1, n2, input_name='foo')])
        self.assertEqual(n2.ein, [Edge(n1, n2, input_name='foo')])

    def test_create_two_named_edges(self):
        """ Create named input/output edges via string multiplication """
        n1, n2 = Node('a'), Node('b')
        result = n1 * 'foo' | 'bar' * n2
        self.assertEqual(result, n2)
        self.assertEqual(n1.eout, [Edge(n1, n2, 'foo', 'bar')])
        self.assertEqual(n2.ein, [Edge(n1, n2, 'foo', 'bar')])

    def test_duplicate_named_input_edge(self):
        """ Assigning an input edge more than once raises an error """
        with self.assertRaises(ValidationError):
            with Graph('g'):
                n1, n2 = Node('a'), Node('b')
                n1 | 'bar' * n2
                n1 * 'foo' | 'bar' * n2

    def test_chained_right(self):
        """ Test a chaining edge case with named output edge """
        n1, n2, n3 = Node('a'), Node('b'), Node('c')
        result = n1 | n2 * 'foo' | n3
        self.assertEqual(n1.eout, [Edge(n1, n2)])
        self.assertEqual(n2.ein, [Edge(n1, n2)])
        self.assertEqual(n2.eout, [Edge(n2, n3, 'foo')])
        self.assertEqual(n3.ein, [Edge(n2, n3, 'foo')])

    def test_not_enough_inputs(self):
        """ If node has insufficient inputs, it fails to validate """
        n = Node('a')
        with self.assertRaises(ValidationError):
            n.validate()
        n.validate(False)

    def test_enough_inputs(self):
        """ If node inputs are satisfied, validation succeeds """
        n = Node('a') | Node('b')
        n.validate()


class TestGraph(unittest.TestCase):

    """ Tests for a complete graph of nodes """

    def test_sort(self):
        """ Sorting nodes puts them in topographical order """
        a, b, c, d = Node('a'), Node('b'), Node('c'), Node('d')
        a | b | c
        a * 'foo' | 'bar' * c
        d | 'baz' * b
        nodes = topo_sort([a, d])
        self.assertEqual(set(nodes[:2]), set([a, d]))
        self.assertEqual(nodes[2:], [b, c])

    def test_graph(self):
        """ Graphs can be used as a context. Nodes are auto-registered. """
        with Graph('g') as graph:
            a = Node('a')
        self.assertEqual(graph._nodes, [a])

    def test_multi_sink(self):
        """ Ambiguous sink nodes cause validation error """
        with self.assertRaises(ValidationError):
            with Graph('g') as graph:
                pike.glob('a', '*')
                pike.glob('b', '*')

    def test_multi_sink_explicit(self):
        """ Explicitly using the sink node fixes ambiguity errors """
        with Graph('g') as graph:
            pike.glob('a', '*') | graph.sink
            pike.glob('b', '*') | 'in2' * graph.sink

    def test_multi_source(self):
        """ Ambiguous source nodes cause validation error """
        with self.assertRaises(ValidationError):
            with Graph('g') as graph:
                Node('a') | graph.sink
                Node('b') | 'out2' * graph.sink

    def test_multi_source_explicit(self):
        """ Explicitly using the source node fixes ambiguity errors """
        with Graph('g') as graph:
            graph.source | Node('a') | graph.sink
            graph.source * 'out2' | Node('b') | 'in2' * graph.sink

    def test_macro(self):
        """ Create a macro that inserts custom nodes for alias nodes """
        with Graph('g') as graph:
            a = AliasNode()
        m = graph.macro(only=a)
        g1 = m(ParrotNode('foo'))
        g2 = m(only=ParrotNode('bar'))
        self.assertEqual(g1.run(), {'default': 'foo'})
        self.assertEqual(g2.run(), {'default': 'bar'})

    def test_double_star_edges(self):
        """ Edges with '*' as names can redirect all outputs to next node """
        value = {'foo': 1, 'bar': 2}
        with Graph('g') as graph:
            p = ParrotNode(value)
            p * '*' | '*' * graph.sink
        ret = graph.run()
        self.assertEqual(ret, value)

    def test_star_output_edge(self):
        """ Edges with '*' as output name creates XargsNode """
        value = {'foo': [1], 'bar': [2]}
        with Graph('g') as graph:
            p = ParrotNode(value)
            p * '*' | pike.map(lambda x: x + 1)
        ret = graph.run()
        self.assertEqual(ret, {'foo': [2], 'bar': [3]})

    def test_star_input_edge(self):
        """ Edges with '*' as just input name are not allowed """
        with self.assertRaises(ValidationError):
            Node('a') | '*' * Node('b')
