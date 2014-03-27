""" Environments for running groups of graphs. """
import copy
import logging

import os
from .dbdict import PersistentDict
from .graph import Graph
from .nodes import FingerprintNode
from .util import resource_spec, memoize
LOG = logging.getLogger(__name__)


class Environment(object):

    def __init__(self):
        self._cache = {}
        self._has_run_all = False
        self._graphs = {}
        self._gen_files = {}
        self.default_output = None

    def add(self, graph, ignore_default_output=False):
        if graph.name in self._graphs:
            raise KeyError("Graph '%s' already exists in environment!" %
                           graph.name)
        if self.default_output is None or ignore_default_output:
            self._graphs[graph.name] = graph
        else:
            with Graph(graph.name + '-wrapper') as wrapper:
                graph * '*' | '*' * self.default_output
            self._graphs[graph.name] = wrapper

    def set_default_output(self, graph):
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
            results = self._graphs[name].run()
            # Remove data to save memory
            for items in results.itervalues():
                for item in items:
                    del item.data
                    # (asset pipeline, location on disk)
                    self._gen_files[item.filename] = (name, item.fullpath)
            self._cache[name] = results
        return self._cache[name]

    def run_all(self, bust=False):
        """ First call runs all pipelines. Successive calls have no effect. """
        if not self._has_run_all or bust:
            self._has_run_all = True
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
        path : str or bool
            Absolute path of the generated asset (if it exists). If the path is
            known to be invalid, this value will be False.

        """
        self.run_all()
        if path not in self._gen_files:
            return False
        name, fullpath = self._gen_files[path]
        if not os.path.exists(fullpath):
            self.run(name, True)
        return fullpath


class DebugEnvironment(Environment):

    """
    Environment implementation that watches source files for changes

    Parameters
    ----------
    cache : str, optional
        Name of the file to cache source file metadata in (default
        '.pike-cache'). This file will be put into the ``output_dir``. This
        file cache greatly speeds up server restarts during development, but it
        may be disabled by passing in ``None``.

    """

    def __init__(self, cache='.pike-cache'):
        super(DebugEnvironment, self).__init__()
        self._cache_file = resource_spec(cache)
        if self._cache_file is None:
            self._disk_cache = {}
        else:
            self._disk_cache = PersistentDict(self._cache_file)
        self._gen_files = self._disk_cache.get('gen_files', {})
        self._fingerprints = self._disk_cache.get('fingerprints', {})
        self._cache = self._disk_cache.get('cache', {})
        self._has_run_all = self._disk_cache.get('has_run_all', False)
        self._fingerprint_graphs = {}

    def _save_cache(self):
        """ Write the cache file """
        if self._cache_file is None:
            return
        self._disk_cache['gen_files'] = self._gen_files
        self._disk_cache['fingerprints'] = self._fingerprints
        self._disk_cache['cache'] = self._cache
        self._disk_cache['has_run_all'] = self._has_run_all
        self._disk_cache.sync()

    def add(self, graph, ignore_default_output=False):
        super(DebugEnvironment, self).add(graph, ignore_default_output)
        with Graph(graph.name + '-hash') as hash_graph:
            finger = FingerprintNode()
            # FIXME: I don't like this. It's hacked as fuck.
            for node in graph.source_nodes():
                copy.copy(node) | finger
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
                LOG.info("Regenerating %s", name)
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

    @memoize(timeout=1)
    def fingerprint(self, name):
        """
        Get the fingerprint for all the source files.

        This is memoized because we check the sources every time we render a
        graph OR attempt to :meth:`~.lookup` an asset. That can happen quite a
        lot, whereas source files are not likely to change more frequently than
        every second.

        """
        graph = self._fingerprint_graphs[name]
        return graph.run()['default']

    def lookup(self, path):
        self.run_all()

        if path in self._gen_files:
            name, fullpath = self._gen_files[path]
            self.run(name, not os.path.exists(fullpath))

        return super(DebugEnvironment, self).lookup(path)
