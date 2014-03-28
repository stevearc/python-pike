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
from .nodes import (FingerprintNode, ChangeListenerNode, ChangeEnforcerNode,
                    CacheNode, Edge, NoopNode)
from .util import resource_spec, memoize


LOG = logging.getLogger(__name__)


def watch_graph(graph, partial=False, cache=None):
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
    with new_graph:
        # If we only pass through the changed files, we'll need a CacheNode at
        # the end
        if partial:
            sink = CacheNode()
            new_graph.sink.connect(sink)
            new_graph.sink = sink
            if cache is not None:
                key = new_graph.name + '_cache'
                if key in cache:
                    sink.cache = cache[key]
                else:
                    cache[key] = sink.cache
        enforcer = ChangeEnforcerNode()
        for i, node in enumerate(new_graph.source_nodes()):
            # Find the outbound edge of the source
            if node.eout:
                edge = node.eout[0]
                edge.remove()
            else:
                # If source has no outbound edge, make one.
                edge = Edge(n2=NoopNode())
            # Funnel files through a change listener
            listener = ChangeListenerNode(stop=False)
            if cache is not None:
                key = new_graph.name + '_listen_' + str(i)
                if key in cache:
                    listener.checksums = cache[key]
                else:
                    cache[key] = listener.checksums
            node.connect(listener)
            # Create a fan-in, fan-out with the changed files that goes through
            # a ChangeEnforcer. That way processing will continue even if only
            # one of the sources has changed files.
            listener.connect(enforcer, input_name=str(i))
            if not partial:
                listener.connect(enforcer, output_name='all', input_name=str(i)
                                 + '_all')
            enforcer.connect(edge.n2, output_name=str(i),
                             input_name=edge.input_name)
    return new_graph


class Environment(object):

    """
    Environment for running multiple Graphs and caching the results.

    """

    def __init__(self, watch=False, cache=None):
        self._disk_cache = None
        self._cache = {}
        self._graphs = {}
        self._gen_files = {}
        if cache is not None:
            self._disk_cache = PersistentDict(cache)
            self._cache = self._disk_cache.setdefault('cache', {})
            self._gen_files = self._disk_cache.setdefault('gen_files', {})
        self.default_output = None
        self.watch = watch

    def add(self, graph, ignore_default_output=False, partial=False):
        """
        Add a graph to the Environment.

        Parameters
        ----------
        graph : :class:`~pike.Graph`
            The graph to add
        ignore_default_output : bool, optional
            If True, will *not* run the ``default_output`` graph on the output
            of this graph (default False)
        partial : bool, optional
            This argument will be passed to :meth:`~.watch_graph`

        """
        if graph.name in self._graphs:
            raise KeyError("Graph '%s' already exists in environment!" %
                           graph.name)
        if self.default_output is not None and not ignore_default_output:
            with Graph(graph.name + '-wrapper') as wrapper:
                graph.connect(self.default_output, '*', '*')
            graph = wrapper
        if self.watch:
            graph = watch_graph(graph, partial, self._disk_cache)

        self._graphs[graph.name] = graph

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
        if bust or self.watch or name not in self._cache:
            LOG.info("Running %s", name)
            try:
                results = self._graphs[name].run()
                LOG.debug("Completed %s", name)
                for items in six.itervalues(results):
                    for item in items:
                        if isinstance(item, FileMeta):
                            # Remove data to save memory
                            if hasattr(item, 'data'):
                                del item.data
                            # (asset pipeline, location on disk)
                            self._gen_files[item.filename] = \
                                (name, item.fullpath)
                self._cache[name] = results
                if self._disk_cache is not None:
                    self._disk_cache.sync()
            except StopProcessing:
                LOG.debug("No changes for %s", name)
        return self._cache[name]

    def run_all(self, bust=False):
        """ Run all graphs. """
        for name in self._graphs:
            self.run(name, bust)

    def run_forever(self, sleep=2, daemon=False):
        """
        Rerun graphs forever, busting the env cache each time.

        This is generally only useful if ``watch=True``.

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
                self.run_all(bust=True)
            except KeyboardInterrupt:
                break
            except Exception:
                LOG.exception("Error while serving forever!")
            time.sleep(sleep)

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
        if path not in self._gen_files:
            if self.watch:
                self.run_all(True)
                if path not in self._gen_files:
                    return None
            else:
                return None
        name, fullpath = self._gen_files[path]
        if self.watch and not os.path.exists(fullpath):
            self.run(name, True)
        return fullpath
