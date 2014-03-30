""" Tests for pike.util """
import six
import os

from .test import BaseFileTest
from pike import util, sqlitedict


class TestFileMatch(BaseFileTest):

    """ Tests for recursive file glob matching """

    def setUp(self):
        super(TestFileMatch, self).setUp()
        self.make_files(
            'app.js',
            'widget.js',
            'common/util.js',
            'common/api.js',
            'shop/models.js',
            'shop/util.js',
        )

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


class TestSqliteDict(BaseFileTest):

    """ Tests for sqlitedict """

    def test_sqlitedict(self):
        """ Run a bunch of tests on sqlitedicts """
        with sqlitedict.open() as d:
            self.assertEqual(list(d), [])
            self.assertEqual(len(d), 0)
            self.assertFalse(d)
            d['abc'] = 'rsvp' * 100
            self.assertEqual(d['abc'], 'rsvp' * 100)
            self.assertEqual(len(d), 1)
            d['abc'] = 'lmno'
            self.assertEqual(d['abc'], 'lmno')
            self.assertEqual(len(d), 1)
            del d['abc']
            self.assertFalse(d)
            self.assertEqual(len(d), 0)
            d['abc'] = 'lmno'
            d['xyz'] = 'pdq'
            self.assertEqual(len(d), 2)
            self.assertItemsEqual(list(six.iteritems(d)), [('abc', 'lmno'),
                                                           ('xyz', 'pdq')])
            self.assertItemsEqual(d.items(), [('abc', 'lmno'), ('xyz', 'pdq')])
            self.assertItemsEqual(d.values(), ['lmno', 'pdq'])
            self.assertItemsEqual(d.keys(), ['abc', 'xyz'])
            self.assertItemsEqual(list(d), ['abc', 'xyz'])
            d.update(p='x', q='y', r='z')
            self.assertEqual(len(d), 5)
            self.assertItemsEqual(d.items(),
                                  [('abc', 'lmno'), ('xyz', 'pdq'),
                                   ('q', 'y'), ('p', 'x'), ('r', 'z')])
            del d['abc']
            try:
                d['abc']
            except KeyError:
                pass
            else:
                assert False
            try:
                del d['abc']
            except KeyError:
                pass
            else:
                assert False
            self.assertItemsEqual(list(d), ['xyz', 'q', 'p', 'r'])
            self.assertTrue(d)
            d.clear()
            self.assertFalse(d)
            self.assertEqual(list(d), [])
            d.update(p='x', q='y', r='z')
            self.assertItemsEqual(list(d), ['q', 'p', 'r'])
            d.clear()
            self.assertFalse(d)

    def test_file_persistence(self):
        """ Dict should be saved to a file """
        with sqlitedict.open('test.db') as d:
            d['abc'] = 'def'

        with sqlitedict.open('test.db') as d:
            self.assertEqual(d['abc'], 'def')

    def test_flag_n(self):
        """ The 'n' flag will clear an existing database """
        with sqlitedict.open('test.db', flag='n') as d:
            d['abc'] = 'def'

        with sqlitedict.open('test.db', flag='n') as d:
            self.assertFalse(d)

    def test_flag_w(self):
        """ The 'w' flag will clear existing table """
        with sqlitedict.open('test.db', 'a') as d:
            d['abc'] = 'def'

        with sqlitedict.open('test.db', 'b') as d:
            d['abc'] = 'def'

        with sqlitedict.open('test.db', 'a', flag='w') as d:
            self.assertFalse(d)
        with sqlitedict.open('test.db', 'b') as d:
            self.assertEqual(d['abc'], 'def')

    def test_bad_flag(self):
        """ Passing a bad flag raises error """
        with self.assertRaises(ValueError):
            sqlitedict.open(flag='g')

    def test_memory(self):
        """ in-memory databases do not create files """
        with sqlitedict.open() as d:
            d['abc'] = 'def'
            self.assertEqual(os.listdir(os.curdir), [])
        self.assertEqual(os.listdir(os.curdir), [])

    def test_autocommit(self):
        """ When autocommit=True the db is automatically updated """
        d1 = sqlitedict.open('test.db', autocommit=True)
        d2 = sqlitedict.open('test.db', autocommit=True)

        d1['abc'] = 'def'
        self.assertEqual(d2['abc'], 'def')

    def test_no_autocommit(self):
        """ When autocommit=False the db is updated when commit() is called """
        d1 = sqlitedict.open('test.db', autocommit=False)
        d2 = sqlitedict.open('test.db', autocommit=False)

        d1['abc'] = 'def'
        self.assertFalse(d2)
        d1.commit()
        self.assertEqual(d2['abc'], 'def')

    def test_commit_after_close(self):
        """ Calling commit() after closing sqlitedict raises error """
        d = sqlitedict.open()
        d.close()
        with self.assertRaises(IOError):
            d.commit()

    def test_close_calls_commit(self):
        """ If autocommit=False, closing sqlitedict automatically commits """
        d1 = sqlitedict.open('test.db', autocommit=False)
        d2 = sqlitedict.open('test.db', autocommit=False)

        d1['abc'] = 'def'
        self.assertFalse(d2)
        d1.close()
        self.assertEqual(d2['abc'], 'def')

    def test_terminate(self):
        """ Calling terminate() removes database file """
        with sqlitedict.open('test.db') as d:
            d['abc'] = 'def'
        d.terminate()
        self.assertFalse(os.path.exists('test.db'))
