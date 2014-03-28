""" Environments for running groups of graphs. """
import os
import time

import copy
import logging
import six
import threading

from .dbdict import PersistentDict
from .exceptions import StopProcessing
from .graph import Graph
from .items import FileMeta
from .nodes import FingerprintNode, ChangeListenerNode, CacheNode
from .util import resource_spec, memoize


LOG = logging.getLogger(__name__)


def watch_graph(graph, partial=False):
    """
    Construct a copy of a graph that will watch source nodes for changes.

    Parameters
    ----------
    graph : :class:`~pike.Graph`
    partial : bool, optional
        If True, the :class:`~pike.ChangeListenerNode` will only propagate
        changed files and the graph will rely on a :class:`~pike.CacheNode` to
        produce the total output.

    """
    new_graph = copy.deepcopy(graph)
    output_name = None if partial else 'all'
    with new_graph:
        for node in new_graph.source_nodes():
            node.insert_after(ChangeListenerNode(), output_name=output_name)
        if partial:
            sink = CacheNode()
            graph.sink | sink
            graph.sink = sink
    return new_graph


class Environment(object):

    """
    Environment for running multiple Graphs and caching the results.

    """

    def __init__(self):
        self._cache = {}
        self._graphs = {}
        self._gen_files = {}
        self.default_output = None

    def add(self, graph, ignore_default_output=False):
        """
        Add a graph to the Environment.

        Parameters
        ----------
        graph : :class:`~pike.Graph`
            The graph to add
        ignore_default_output : bool, optional
            If True, will *not* run the ``default_output`` graph on the output
            of this graph (default False)

        """
        if graph.name in self._graphs:
            raise KeyError("Graph '%s' already exists in environment!" %
                           graph.name)
        if self.default_output is None or ignore_default_output:
            self._graphs[graph.name] = graph
        else:
            with Graph(graph.name + '-wrapper') as wrapper:
                graph.connect(self.default_output, '*', '*')
            self._graphs[graph.name] = wrapper

    def set_default_output(self, graph):
        """
        Set a default operation to be run after every graph.

        By default, every time you :meth:`~.add` a Graph, that Graph will have
        this process tacked on to the end. This can be used to do common
        operations, such as writing files or generating urls.

        Parameters
        ----------
        graph : :class:`~pike.Graph` or :class:`~pike.Node`
            The graph to run after other graphs.

        """
        self.default_output = graph

    def run(self, name, bust=False):
        """
        Run a graph and cache the result.

        Returns the cached result if one exists.

        Parameters
        ----------
        name : str
            Name of the graph to run
        bust : bool, optional
            If True, will ignore the cache and rerun (default False)

        Returns
        -------
        results : dict
            Same output as the graph

        """
        if name not in self._cache or bust:
            LOG.info("Running %s", name)
            try:
                results = self._graphs[name].run()
                # Remove data to save memory
                for items in six.itervalues(results):
                    for item in items:
                        if isinstance(item, FileMeta):
                            del item.data
                            # (asset pipeline, location on disk)
                            self._gen_files[item.filename] = (name, item.fullpath)
                self._cache[name] = results
            except StopProcessing:
                pass
        return self._cache[name]

    def run_all(self, bust=False):
        """ Run all graphs. """
        for name in self._graphs:
            self.run(name, bust)

    def lookup(self, path):
        """
        Get a generated asset path

        Parameters
        ----------
        path : str
            Relative path of the asset

        Returns
        -------
        path : str or None
            Absolute path of the generated asset (if it exists). If the path is
            known to be invalid, this value will be None.

        """
        self.run_all()
        if path not in self._gen_files:
            return False
        fullpath = self._gen_files[path][1]
        return fullpath


class DebugEnvironment(Environment):

    """
    Environment implementation that watches source files for changes.

    When a Graph is added to the Environment, all source nodes inside the graph
    will be monitored. When one or more of them have changes in their files,
    the graph is run again.

    Parameters
    ----------
    cache : str, optional
        Name of the file to cache source file metadata in (default
        '.pike-cache'). This file cache greatly speeds up server restarts
        during development, but it may be disabled by passing in ``None``.

    """

    def __init__(self, cache='.pike-cache'):
        super(DebugEnvironment, self).__init__()
        if cache is None:
            self._cache_file = None
            self._disk_cache = {}
        else:
            self._cache_file = resource_spec(cache)
            self._disk_cache = PersistentDict(self._cache_file)
        self._gen_files = self._disk_cache.get('gen_files', {})
        self._fingerprints = self._disk_cache.get('fingerprints', {})
        self._cache = self._disk_cache.get('cache', {})
        self._fingerprint_graphs = {}

    def _save_cache(self):
        """ Write the cache file """
        if self._cache_file is None:
            return
        self._disk_cache['gen_files'] = self._gen_files
        self._disk_cache['fingerprints'] = self._fingerprints
        self._disk_cache['cache'] = self._cache
        self._disk_cache.sync()

    def add(self, graph, ignore_default_output=False):
        super(DebugEnvironment, self).add(graph, ignore_default_output)
        # Create another graph that fingerprints all the source nodes found
        with Graph(graph.name + '-hash') as hash_graph:
            finger = FingerprintNode()
            for node in graph.source_nodes():
                copy.copy(node).connect(finger)
        self._fingerprint_graphs[graph.name] = hash_graph

    def run_all(self, bust=False):
        super(DebugEnvironment, self).run_all(bust)
        self._save_cache()

    def run(self, name, bust=False):
        bust = bust or name not in self._cache
        if not bust or name not in self._fingerprints:
            new = self.fingerprint(name)
            old = self._fingerprints.get(name)

            if new != old:
                LOG.info("'%s' fingerprint changed", name)
                self._fingerprints[name] = new
                bust = True

        try:
            results = super(DebugEnvironment, self).run(name, bust)
        except Exception as e:
            if hasattr(e, 'pipeline'):
                e.message += '\n%s' % ' -> '.join((str(n) for n in
                                                   reversed(e.pipeline)))
            raise
        if bust:
            self._save_cache()
        return results

    def run_forever(self, sleep=2, daemon=False):
        """
        Run graphs on changes forever.

        Parameters
        ----------
        sleep : int, optional
            How long to sleep between runs. Default 2 seconds.
        daemon : bool, optional
            If True, will run in a background thread (default False)

        """
        if daemon:
            thread = threading.Thread(target=self.run_forever,
                                      kwargs={'sleep': sleep})
            thread.daemon = True
            thread.start()
            return thread
        while True:
            try:
                self.run_all()
                time.sleep(sleep)
            except KeyboardInterrupt:
                break
            except Exception:
                LOG.exception("Error while serving forever!")

    @memoize(timeout=2)
    def fingerprint(self, name):
        """
        Get the fingerprint for all the source files.

        This is memoized because we check the sources every time we run a graph
        OR attempt to :meth:`~.lookup` a file. That can happen quite a lot,
        whereas source files are not likely to change more frequently than
        every couple seconds.

        """
        LOG.debug("Fingerprinting %s", name)
        graph = self._fingerprint_graphs[name]
        return graph.run()['default']

    def lookup(self, path):
        self.run_all()

        if path in self._gen_files:
            name, fullpath = self._gen_files[path]
            self.run(name, not os.path.exists(fullpath))
            return fullpath
        return False
