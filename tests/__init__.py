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
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        super(BaseFileTest, self).tearDown()
        shutil.rmtree(self.tempdir)

    def _make_files(self, *files):
        """ Shortcut to create files on disk """
        for filename in files:
            filename = os.path.join(self.tempdir, filename)
            basename = os.path.dirname(filename)
            if not os.path.exists(basename):
                os.makedirs(basename)
            with open(filename, 'w') as ofile:
                ofile.write('foo')

# pylint: disable=E1101
if six.PY3:  # pragma: no cover
    unittest.TestCase.assertItemsEqual = unittest.TestCase.assertCountEqual
