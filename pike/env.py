""" Environments for running groups of graphs. """
import os
import time
from datetime import datetime

import copy
import logging
import six
import tempfile
import threading
from six.moves import cPickle as pickle  # pylint: disable=F0401

from .exceptions import StopProcessing
from .items import FileMeta
from .nodes import (ChangeListenerNode, ChangeEnforcerNode, CacheNode, Edge,
                    NoopNode)
from .sqlitedict import SqliteDict


LOG = logging.getLogger(__name__)


def commit(cache):
    """ Commit if SqliteDict, else do nothing. """
    try:
        cache.commit()
    except AttributeError:
        pass


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
            new_graph.sink.connect(sink, '*', '*')
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


class IExceptionHandler(object):

    """
    Interface for exception handlers.

    This class can intercept exceptions raised while running a graph in an
    environment and perform some processing.

    """

    def handle_exception(self, graph, exc, node):
        """
        Handle an exception.

        Parameters
        ----------
        graph : :class:`~pike.graph.Graph`
        exc : :class:`Exception`
        node : :class:`~pike.nodes.base.Node`

        Returns
        -------
        handled : bool
            If True, the Environment will not raise the exception

        """
        raise NotImplementedError


def apply_error_style(node, error_style):
    """
    Apply error styles to a graph.

    Parameters
    ----------
    node : :class:`~pike.nodes.base.Node`
        The node that threw the exception
    error_style : dict
        The styles to apply to nodes and edges involved in the traceback.

    Returns
    -------
    style : dict
        Style dict for passing to :meth:`pike.graph.Graph.dot`.

    """
    styles = {}
    for node in node.walk_up(True):
        styles[node] = error_style
        for edge in node.ein:
            styles[edge] = error_style
    return styles


class RenderException(IExceptionHandler):

    """
    Render traceback as a png in a directory.

    Parameters
    ----------
    output_dir : str, optional
        Directory to render exception into (defaults to temporary directory)
    error_style : dict, optional
        Dict of attributes to apply to nodes and edges involved in the
        traceback (default {'color': 'red'}).

    """

    def __init__(self, output_dir=None, error_style=None):
        super(RenderException, self).__init__()
        self.error_style = error_style or {'color': 'red'}
        if output_dir is None:
            self.output_dir = tempfile.gettempdir()
        else:
            self.output_dir = output_dir

    def handle_exception(self, graph, exc, node):
        filename = 'exc_%s.png' % datetime.now().isoformat()
        fullpath = os.path.join(self.output_dir, filename)
        styles = apply_error_style(node, self.error_style)
        graph.render(fullpath, style=styles)
        LOG.error("Exception rendered as %s", fullpath)


class ShowException(IExceptionHandler):

    """
    When an exception occurs, this will auto-open the visual traceback.

    Parameters
    ----------
    error_style : dict, optional
        Dict of attributes to apply to nodes and edges involved in the
        traceback (default {'color': 'red'}).
    **kwargs : dict, optional
        These will be passed to :meth:`~pike.graph.Graph.show`

    """

    def __init__(self, error_style=None, show_kwargs=None):
        super(ShowException, self).__init__()
        self.error_style = error_style or {'color': 'red'}
        self.show_kwargs = show_kwargs or {}

    def handle_exception(self, graph, exc, node):
        styles = apply_error_style(node, self.error_style)
        graph.show(style=styles, **self.show_kwargs)


class Environment(object):

    """
    Environment for running multiple Graphs and caching the results.

    Parameters
    ----------
    watch : bool, optional
        If True, watch all graphs for changes in the source files and rerun
        them if changes are detected (default False)
    cache : str, optional
        The sqlite file to use as a persistent cache (defaults to in-memory
        dict)
    fingerprint : str or callable, optional
        The method to use for fingerprinting files when ``watch=True``. See
        :class:`~pike.nodes.watch.ChangeListenerNode` for details. (default
        'md5')
    exception_handler : :class:`~.IExceptionHandler`, optional
        When running a graph throws an exception, this handler will do
        something useful. The default handler will attempt to render a png of
        the traceback to a temporary directory. Set to ``None`` to do nothing.

    Notes
    -----

    """

    def __init__(self,
                 watch=False,
                 cache=None,
                 fingerprint='md5',
                 exception_handler=RenderException(),
                 ):
        self._fingerprint = fingerprint
        self._graphs = {}
        self._cache_file = cache
        if cache is not None:
            self._cache = SqliteDict(cache, 'processed', autocommit=False,
                                     synchronous=0)
            self._gen_files = SqliteDict(cache, 'file_paths', autocommit=False,
                                         synchronous=0)
        else:
            self._cache = {}
            self._gen_files = {}
        self.default_output = None
        self.watch = watch
        self._exc_handler = exception_handler

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
            wrapper = copy.deepcopy(graph)
            wrapper.name += '-wrapper'
            with wrapper:
                edge = wrapper.sink.connect(self.default_output, '*', '*')
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

    def get(self, name):
        """ Get the cached results of a graph. """
        return self._cache.get(name)

    def save(self, filename):
        """ Saved the cached asset metadata to a file """
        self.run_all(True)
        with open(filename, 'wb') as ofile:
            pickle.dump(dict(self._cache), ofile)

    def load(self, filename):
        """ Load cached asset metadata from a file """
        with open(filename, 'rb') as ifile:
            self._cache = pickle.load(ifile)

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
            LOG.debug("Running %s", name)
            try:
                start = time.time() * 1000
                results = self._graphs[name].run()
                elapsed = int(time.time() * 1000 - start)
                LOG.info("Ran %s in %d ms", name, elapsed)
                for items in six.itervalues(results):
                    for item in items:
                        if isinstance(item, FileMeta):
                            # Remove data to save memory
                            if hasattr(item, 'data'):
                                del item.data
                            self._gen_files[item.filename] = item.fullpath
                commit(self._gen_files)
                self._cache[name] = results
                commit(self._cache)
            except StopProcessing:
                LOG.debug("No changes for %s", name)
            except Exception as e:
                if hasattr(e, 'node') and self._exc_handler is not None:
                    LOG.error("Exception at node %s", e.node)
                    graph = self._graphs[name]
                    ret = False
                    try:
                        ret = self._exc_handler.handle_exception(graph, e,
                                                                 e.node)
                    except Exception:
                        LOG.exception("Error while handling exception")
                    if not ret:
                        raise e
                else:
                    raise
        return self._cache.get(name)

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
        for fullpath in six.itervalues(self._gen_files):
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

    def run_forever(self, sleep=2, daemon=False, daemon_proc=False):
        """
        Rerun graphs forever, busting the env cache each time.

        This is generally only useful if ``watch=True``.

        Parameters
        ----------
        sleep : int, optional
            How long to sleep between runs. Default 2 seconds.
        daemon : bool, optional
            If True, will run in a background thread (default False)
        daemon_proc : bool, optional
            If True, will run in a child process (default False)

        """
        if daemon and daemon_proc:
            raise TypeError("daemon and daemon_proc cannot both be True")
        if daemon:
            thread = threading.Thread(target=self.run_forever,
                                      kwargs={'sleep': sleep})
            thread.daemon = True
            thread.start()
            return thread
        elif daemon_proc:
            pid = os.fork()
            if pid != 0:
                return pid
        while True:
            try:
                self.run_all(bust=True)
            except KeyboardInterrupt:
                break
            except Exception:
                LOG.exception("Error while running forever!")
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
            return None
        fullpath = self._gen_files[path]
        return fullpath
