""" Tests for pike """
import os

import shutil
import six
import tempfile

from pike import Node


try:
    import unittest2 as unittest  # pylint: disable=F0401
except ImportError:
    import unittest


class ParrotNode(Node):

    """ Dummy node that just spits out a preset value """

    name = 'parrot'

    def __init__(self, value):
        super(ParrotNode, self).__init__()
        self.value = value

    def process(self, default=None, **kwargs):
        return self.value


class BaseFileTest(unittest.TestCase):

    """ Base test that makes it easy to create files """

    def setUp(self):
        super(BaseFileTest, self).setUp()
        self.prevdir = os.getcwd()
        self.tempdir = tempfile.mkdtemp()
        os.chdir(self.tempdir)

    def tearDown(self):
        super(BaseFileTest, self).tearDown()
        os.chdir(self.prevdir)
        shutil.rmtree(self.tempdir)

    def make_files(self, *files, **kwargs):
        """
        Shortcut to create files on disk.

        You can pass it filenames (they will contain the string 'foo') or
        dictionaries mapping filenames to file data.

        """
        for filename in files:
            if isinstance(filename, dict):
                self.make_files(**filename)
            else:
                self.make_files(**{filename: 'foo'})

        for filename, data in six.iteritems(kwargs):
            filename = os.path.join(self.tempdir, filename)
            basename = os.path.dirname(filename)
            if not os.path.exists(basename):
                os.makedirs(basename)
            with open(filename, 'w') as ofile:
                ofile.write(data)

    def assert_files_equal(self, first, second, msg=None):
        """ Assert that a list of ``FileMeta`` objects has these file paths """
        paths = [os.path.abspath(item.fullpath) for item in first]
        abspaths = map(os.path.abspath, second)
        self.assertItemsEqual(paths, abspaths, msg)

# pylint: disable=E1101
if six.PY3:  # pragma: no cover
    unittest.TestCase.assertItemsEqual = unittest.TestCase.assertCountEqual
