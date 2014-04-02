#
# Originally pulled from https://github.com/piskvorky/sqlitedict
# Copyright (C) 2011 Radim Rehurek <radimrehurek@seznam.cz>

# Hacked together from:
#  * http://code.activestate.com/recipes/576638-draft-for-an-sqlite3-based-dbm/
#  * http://code.activestate.com/recipes/526618/
#
# Use the code in any way you like (at your own risk), it's public domain.

""" A lightweight wrapper around sqlite3, with a dict-like interface """
# pylint: disable=F0401,E0611,C0103,C0111
import os
import re

import logging
import six
import sqlite3
from collections import MutableMapping
from six.moves.cPickle import dumps, loads, HIGHEST_PROTOCOL as PICKLE_PROTOCOL


# pylint: enable=F0401,E0611

__queries__ = {
    'MAKE_TABLE': 'CREATE TABLE IF NOT EXISTS %s '
                  '(key TEXT PRIMARY KEY, value BLOB)',
    'GET_LEN': 'SELECT COUNT(*) FROM %s',
    'GET_FIRST': 'SELECT MAX(ROWID) FROM %s',
    'GET_ITEM': 'SELECT value FROM %s WHERE key = ?',
    'ADD_ITEM': 'REPLACE INTO %s (key, value) VALUES (?,?)',
    'DEL_ITEM': 'DELETE FROM %s WHERE key = ?',
    'UPDATE_ITEMS': 'REPLACE INTO %s (key, value) VALUES (?, ?)',
    'GET_KEYS': 'SELECT key FROM %s ORDER BY rowid',
    'CLEAR_ALL': 'DELETE FROM %s',
}

LOG = logging.getLogger('sqlitedict')


class Namespace(dict):

    """ Dict with attribute access """

    def __getattr__(self, key):
        return self[key]


def open(*args, **kwargs):
    """See documentation of the SqlDict class."""
    return SqliteDict(*args, **kwargs)


def encode(obj):
    """Serialize an object using pickle to a binary format accepted by SQLite."""
    return sqlite3.Binary(dumps(obj, protocol=PICKLE_PROTOCOL))


def decode(obj):
    """Deserialize objects retrieved from SQLite."""
    return loads(six.binary_type(obj))


class SqliteDict(MutableMapping):

    """
    Dictionary backed by sqlite

    Parameters
    ----------
    filename : str, optional
        The name of the database file (default ':memory:')
    tablename : str, optional
        The name of the table in the database to use (default 'unnamed')
    flag : {'c', 'w', 'n'}, optional
        +-----+----------------------------------------------------+
        | 'c' | create the database file if needed                 |
        | 'w' | drop the ``tablename`` contents upon opening       |
        | 'n' | erase existing file at ``filename`` if present     |
        +-----+----------------------------------------------------+
    autocommit : bool, optional
        If False, you must manually call :meth:`~.commit` to commit any changes
        (default True)
    journal_mode : str, optional
        Any valid value from `the sqlite docs
        <http://www.sqlite.org/pragma.html#pragma_journal_mode>`_ (default
        'DELETE')
    synchronous : int, optional
        Any valid value from `the sqlite docs
        <http://www.sqlite.org/pragma.html#pragma_synchronous>`_ (default 2)

    """

    def __init__(self, filename=':memory:', tablename='unnamed', flag='c',
                 autocommit=True, journal_mode="DELETE", synchronous=2):
        if flag not in ('c', 'w', 'n'):
            raise ValueError("Invalid flag '%s'" % flag)
        if flag == 'n':
            if os.path.exists(filename):
                os.remove(filename)
        tablename = re.sub(r'[^A-Za-z0-9]', '_', tablename)
        self.filename = filename
        self.tablename = tablename
        self.autocommit = autocommit
        self.q = Namespace(dict(((k, v % tablename) for k, v in
                                 six.iteritems(__queries__))))

        # If containing directory doesn't exist, make it
        dirname = os.path.dirname(filename)
        if not os.path.exists(dirname):
            try:
                os.makedirs(dirname)
            except os.error:
                pass

        LOG.debug("opening Sqlite table %r in %s", tablename, filename)
        if autocommit:
            self.conn = sqlite3.connect(self.filename, isolation_level=None,
                                        check_same_thread=False)
        else:
            self.conn = sqlite3.connect(self.filename, check_same_thread=False)
        self.conn.execute('PRAGMA journal_mode = %s' % journal_mode)
        self.conn.text_factory = six.text_type
        self.execute('PRAGMA synchronous=%s' % synchronous)
        self.execute(self.q.MAKE_TABLE)
        self.commit()
        if flag == 'w':
            self.clear()

    def select_one(self, req, arg=()):
        for result in self.execute(req, arg):
            return result
        return None

    def execute(self, req, arg=()):
        cursor = self.conn.cursor()
        cursor.execute(req, arg)
        if self.autocommit:
            self.conn.commit()
        return cursor

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def __repr__(self):
        return "SqliteDict(%s, %s)" % (self.filename, self.tablename)

    def __len__(self):
        # `select count (*)` is super slow in sqlite (does a linear scan!!). As
        # a result, len() is very slow too once the table size grows beyond
        # trivial.  We could keep the total count of rows ourselves, by means
        # of triggers, but that seems too complicated and would slow down
        # normal operation (insert/delete etc).
        rows = self.select_one(self.q.GET_LEN)[0]
        return rows if rows is not None else 0

    def __bool__(self):
        return self.select_one(self.q.GET_FIRST)[0] is not None

    __nonzero__ = __bool__

    def __getitem__(self, key):
        item = self.select_one(self.q.GET_ITEM, (key,))
        if item is None:
            raise KeyError(key)

        return decode(item[0])

    def __setitem__(self, key, value):
        self.execute(self.q.ADD_ITEM, (key, encode(value)))

    def __delitem__(self, key):
        if key not in self:
            raise KeyError(key)
        self.execute(self.q.DEL_ITEM, (key,))

    def __iter__(self):
        for key in self.execute(self.q.GET_KEYS):
            yield key[0]

    def clear(self):
        # avoid VACUUM, as it gives "OperationalError: database schema has
        # changed"
        self.commit()
        self.execute(self.q.CLEAR_ALL)
        self.commit()

    def commit(self):
        if self.conn is None:
            raise IOError("%s is already closed!" % self)
        self.conn.commit()

    sync = commit

    def close(self):
        LOG.debug("closing %s", self)
        if self.conn is not None:
            if not self.autocommit:
                self.commit()
            self.conn.close()
            self.conn = None

    def terminate(self):
        """Delete the underlying database file. Use with care."""
        self.close()
        LOG.info("deleting %s", self.filename)
        os.remove(self.filename)
