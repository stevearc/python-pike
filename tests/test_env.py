""" Tests for the pike environment """
import os

from mock import MagicMock

import pike
from . import ParrotNode, BaseFileTest


class TestEnvironment(BaseFileTest):

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

        # Busting cache should return new value
        ret = env.run('g', True)
        self.assertEqual(ret, {'default': [1, 2]})

    def test_watch_graph_caches(self):
        """ Watching a graph will raise StopProcessing if no file changes """
        self._make_files(foo='foo', bar='bar')
        with pike.Graph('g') as graph:
            pike.glob('.', '*')
        watcher = pike.watch_graph(graph)
        ret = watcher.run()
        self.assertEqual(len(ret['default']), 2)
        with self.assertRaises(pike.StopProcessing):
            watcher.run()

    def test_watch_graph_changes(self):
        """ Watching a graph will return new files if files change """
        self._make_files(foo='foo', bar='bar')
        with pike.Graph('g') as graph:
            pike.glob('.', '*')
        watcher = pike.watch_graph(graph)
        ret = watcher.run()
        self.assertItemsEqual([f.data.read() for f in ret['default']],
                              ['foo', 'bar'])
        self._make_files(foo='foo', bar='foo')
        ret = watcher.run()
        self.assertItemsEqual([f.data.read() for f in ret['default']],
                              ['foo', 'foo'])

    def test_watch_graph_partial_changes(self):
        """ Watching a graph with partial runs will return new files """
        self._make_files(foo='foo', bar='bar')
        with pike.Graph('g') as graph:
            pike.glob('.', '*')
        watcher = pike.watch_graph(graph, partial=True)
        ret = watcher.run()
        self.assertItemsEqual([f.data.read() for f in ret['default']],
                              ['foo', 'bar'])
        self._make_files(foo='foo', bar='foo')
        ret = watcher.run()
        self.assertItemsEqual([f.data.read() for f in ret['default']],
                              ['foo', 'foo'])

    def test_unique(self):
        """ Graphs must have unique names in an Environment """
        env = pike.Environment()
        with pike.Graph('g') as graph:
            pike.glob('.', '*')
        env.add(graph)
        with self.assertRaises(KeyError):
            env.add(graph)

    def test_lookup(self):
        """ Lookup returns full file path """
        env = pike.Environment()
        self._make_files('foo')
        with pike.Graph('g') as graph:
            pike.glob('.', '*')
        env.add(graph)
        env.run_all()
        ret = env.lookup('foo')
        self.assertEqual(ret, os.path.join('.', 'foo'))

    def test_lookup_missing(self):
        """ Lookup if missing returns None """
        env = pike.Environment()
        with pike.Graph('g') as graph:
            pike.glob('.', '*')
        env.add(graph)
        env.run_all()
        ret = env.lookup('foo')
        self.assertIsNone(ret)

    def test_lookup_missing_watch(self):
        """ Lookup if missing reruns graphs if watch=True """
        env = pike.Environment(watch=True)
        self._make_files('foo')
        with pike.Graph('g') as graph:
            pike.glob('.', '*')
        env.add(graph)
        ret = env.lookup('foo')
        self.assertEqual(ret, os.path.join('.', 'foo'))
        ret = env.lookup('bar')
        self.assertIsNone(ret)

    def test_default_output(self):
        """ Default output is auto appended to all graphs """
        env = pike.Environment()
        output = pike.Graph('output')
        output.sink = pike.noop()
        output.run = MagicMock(return_value=[])
        env.set_default_output(output)
        with pike.Graph('g') as graph:
            pike.glob('.', '*')
        env.add(graph)
        env.run_all()
        output.run.assert_called_with([])
