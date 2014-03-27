""" Tests for pike.util """
import os

import shutil
import tempfile

from pike import util


try:
    import unittest2 as unittest  # pylint: disable=F0401
except ImportError:
    import unittest


class TestFileMatch(unittest.TestCase):

    """ Tests for recursive file glob matching """

    def setUp(self):
        super(TestFileMatch, self).setUp()
        self.tempdir = tempfile.mkdtemp()
        self._make_files(
            'app.js',
            'widget.js',
            'common/util.js',
            'common/api.js',
            'shop/models.js',
            'shop/util.js',
        )

    def tearDown(self):
        super(TestFileMatch, self).tearDown()
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

    def test_prefix(self):
        """ Can select files limited by directory prefix """
        results = util.recursive_glob(self.tempdir, '*', 'common')
        self.assertItemsEqual(results, ['common/util.js', 'common/api.js'])

    def test_prefix_in_glob(self):
        """ Can embed a prefix inside the search glob """
        results = util.recursive_glob(self.tempdir, 'common/*')
        self.assertItemsEqual(results, ['common/util.js', 'common/api.js'])

    def test_prefix_and_invert(self):
        """ Can both invert the match and provide a prefix """
        results = util.recursive_glob(self.tempdir, '*.js:!common/*:!shop/*')
        self.assertItemsEqual(results, ['app.js', 'widget.js'])

    def test_match(self):
        """ Globs match filenames """
        results = util.recursive_glob(self.tempdir, 'util.js')
        self.assertItemsEqual(results, ['common/util.js', 'shop/util.js'])

    def test_pathsep(self):
        """ Patterns can be separated by a ':' """
        results = util.recursive_glob(self.tempdir, 'app.js:widget.js')
        self.assertEquals(results, ['app.js', 'widget.js'])

    def test_pattern_list(self):
        """ Patterns can be provided as a list """
        results = util.recursive_glob(self.tempdir, ['app.js', 'widget.js'])
        self.assertEquals(results, ['app.js', 'widget.js'])

    def test_invert_match(self):
        """ Prefixing a glob with ! will remove matching elements """
        results = util.recursive_glob(self.tempdir, 'app.js:!*.js')
        self.assertEquals(results, [])

    def test_dedupe(self):
        """ Results should not contain duplicates """
        results = util.recursive_glob(self.tempdir, 'app.js:app.js')
        self.assertEquals(results, ['app.js'])
