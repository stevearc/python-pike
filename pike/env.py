""" Environments for running groups of graphs. """
import os
import time

import copy
import logging
import six
import threading

from .exceptions import StopProcessing
from .graph import Graph
from .items import FileMeta
from .nodes import (ChangeListenerNode, ChangeEnforcerNode, CacheNode, Edge,
                    NoopNode)
from .sqlitedict import SqliteDict


LOG = logging.getLogger(__name__)


def watch_graph(graph, partial=False, cache=None, fingerprint='md5'):
    """
    Construct a copy of a graph that will watch source nodes for changes.

    Parameters
    ----------
    graph : :class:`~pike.Graph`
    partial : bool, optional
        If True, the :class:`~pike.ChangeListenerNode` will only propagate
        changed files and the graph will rely on a :class:`~pike.CacheNode` to
        produce the total output.
    cache : str, optional
        If present, cache the file fingerprints and other data in this file.
    fingerprint : str or callable, optional
        The method to use for fingerprinting files when ``watch=True``. See
        :class:`~pike.nodes.watch.ChangeListenerNode` for details. (default
        'md5')

    """
    new_graph = copy.deepcopy(graph)
    with new_graph:
        # If we only pass through the changed files, we'll need a CacheNode at
        # the end
        if partial:
            sink = CacheNode(cache, new_graph.name + '_cache')
            new_graph.sink.connect(sink)
            new_graph.sink = sink
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
            key = new_graph.name + '_listen_' + str(i)
            listener = ChangeListenerNode(stop=False, cache=cache, key=key,
                                          fingerprint=fingerprint)
            node.connect(listener)
            # Create a fan-in, fan-out with the changed files that goes through
            # a ChangeEnforcer. That way processing will continue even if only
            # one of the sources has changed files.
            listener.connect(enforcer, input_name=str(i))
            if not partial:
                listener.connect(enforcer, output_name='all', input_name=str(i)
                                 + '_all')
            input_name = edge.input_name
            if input_name == '*':
                input_name = None
            enforcer.connect(edge.n2, output_name=str(i),
                             input_name=input_name)
    return new_graph


class Environment(object):

    """
    Environment for running multiple Graphs and caching the results.

    Parameters
    ----------
    watch : bool, optional
        If True, watch all graphs for changes in the source files and rerun
        them if changes are detected (default False)
    cache : str, optional
        The sqlite file to use as a persistent cache (default ':memory:')
    fingerprint : str or callable, optional
        The method to use for fingerprinting files when ``watch=True``. See
        :class:`~pike.nodes.watch.ChangeListenerNode` for details. (default
        'md5')
    throttle : int, optional
        If ``watch=True``, only re-run graphs once-per-``throttle`` seconds
        (default 2).

    """

    def __init__(self, watch=False, cache=':memory:', fingerprint='md5',
                 throttle=2):
        self._fingerprint = fingerprint
        self._graphs = {}
        self._cache_file = cache
        self._cache = SqliteDict(cache, 'processed', autocommit=False,
                                 synchronous=0)
        self._gen_files = SqliteDict(cache, 'file_paths', autocommit=False,
                                     synchronous=0)
        self.default_output = None
        self.watch = watch
        self._expires = {}
        self._throttle = 2

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
        name = graph.name
        if name in self._graphs:
            raise KeyError("Graph '%s' already exists in environment!" %
                           graph.name)
        if self.default_output is not None and not ignore_default_output:
            with Graph(name + '-wrapper') as wrapper:
                graph.connect(self.default_output, '*', '*')
            graph = wrapper
        if self.watch:
            graph = watch_graph(graph, partial, self._cache_file,
                                self._fingerprint)

        self._graphs[name] = graph

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
        # Throttle runs if watch=True
        if self.watch:
            if self._expires.get(name, 0) > time.time():
                return self._cache[name]

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
                self._gen_files.commit()
                self._cache[name] = results
                self._cache.commit()
            except StopProcessing:
                LOG.debug("No changes for %s", name)
            except Exception as e:
                if hasattr(e, 'path'):
                    LOG.error("Exception along path %s",
                              ' -> '.join([str(node) for node in e.path]))
                raise
        if self.watch:
            self._expires[name] = time.time() + self._throttle
        return self._cache[name]

    def run_all(self, bust=False):
        """ Run all graphs. """
        for name in self._graphs:
            self.run(name, bust)

    def clean(self, directory, dry_run=False):
        """
        Remove all files in a directory that were not generated by the env

        Parameters
        ----------
        directory : str
            The location to look for unnecessary files
        dry_run : bool, optional
            If True, will not actually delete the files (default False)

        Returns
        -------
        removed : list
            List of file paths that were deleted by the operation

        Raises
        ------
        exc : :class:`~ValueError`
            If there are no known generated files. That would delete all files
            in the directory, which is probably not the intended behavior.

        """
        if not self._gen_files:
            raise ValueError("No generated files found. Have you run "
                             "`run_all()`?")
        all_files = set()
        for _, fullpath in six.itervalues(self._gen_files):
            all_files.add(os.path.abspath(fullpath))
        removed = []
        for root, _, files in os.walk(directory):
            for filename in files:
                fullpath = os.path.abspath(os.path.join(root, filename))
                if fullpath not in all_files:
                    removed.append(fullpath)
                    if not dry_run:
                        LOG.info("Removing %s", fullpath)
                        os.remove(fullpath)
        return removed

    def run_forever(self, daemon=False):
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
            thread = threading.Thread(target=self.run_forever)
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
            time.sleep(self._throttle)

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
        if self.watch:
            self.run_all(True)
        if path not in self._gen_files:
            return None
        fullpath = self._gen_files[path][1]
        return fullpath
