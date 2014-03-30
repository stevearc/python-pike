""" Tests for pike.nodes.watch """
import subprocess

import pike
from pike.test import BaseFileTest


class TestChangeListener(BaseFileTest):

    """ Tests for the ChangeListenerNode """

    def test_no_change(self):
        """ If no files change, return no files """
        with pike.Graph('g') as graph:
            pike.glob('.', '*') | pike.ChangeListenerNode(stop=False)
        self.make_files('foo')
        ret = graph.run()
        self.assert_files_equal(ret['default'], ['foo'])
        ret = graph.run()
        self.assert_files_equal(ret['default'], [])

    def test_change_data(self):
        """ If file data changes, it is passed on """
        with pike.Graph('g') as graph:
            pike.glob('.', '*') | pike.ChangeListenerNode()
        self.make_files(foo='a', bar='b')
        ret = graph.run()
        self.assert_files_equal(ret['default'], ['foo', 'bar'])
        self.make_files(foo='asdf', bar='b')
        ret = graph.run()
        self.assert_files_equal(ret['default'], ['foo'])

    def test_change_mtime(self):
        """ If watching mtime, update on mtime change """
        with pike.Graph('g') as graph:
            pike.glob('.', '*') | pike.ChangeListenerNode(fingerprint='mtime')
        self.make_files(foo='a', bar='b')
        ret = graph.run()
        self.assert_files_equal(ret['default'], ['foo', 'bar'])
        subprocess.check_call(['touch', 'foo'])
        ret = graph.run()
        self.assert_files_equal(ret['default'], ['foo'])
