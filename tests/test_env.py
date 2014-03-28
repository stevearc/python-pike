""" Tests for the pike environment """
import pike
from . import ParrotNode
try:
    import unittest2 as unittest  # pylint: disable=F0401
except ImportError:
    import unittest


class TestEnvironment(unittest.TestCase):

    """ Tests for the environment """

    def test_cache_results(self):
        """ Environment should cache results """
        env = pike.Environment()
        value = [1]
        with pike.Graph('g') as graph:
            n = ParrotNode(value)
        env.add(graph)
        ret = env.run('g')
        self.assertEqual(ret, {'default': [1]})
        n.value = [1, 2]
        # We mutated value, but the return value should be cached
        ret = env.run('g')
        self.assertEqual(ret, {'default': [1]})


class TestDebugEnvironment(unittest.TestCase):

    """ Tests for the debug environment """
