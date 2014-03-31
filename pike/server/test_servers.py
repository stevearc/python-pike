""" Integration tests for server extensions """
import os
import sys

import six
import webtest
from pyramid.config import Configurator

import pike
from pike.test import BaseFileTest


try:
    import unittest2 as unittest  # pylint: disable=F0401
except ImportError:
    import unittest


class TestPyramid(BaseFileTest):

    """ Tests for the pyramid extension """

    def _run_test(self, settings):
        """ Run a simple pyramid app and check that serving files works """
        config = Configurator(settings=settings)
        config.include('pike')
        files = {
            'foo.html': b'<h1>hello world</h1>',
            'foo.js': b"alert('hello world');",
        }
        self.make_files(files)
        env = config.get_pike_env()
        with pike.Graph('assets') as graph:
            pike.glob('.', '*')
        env.add(graph)
        env.run_all()

        app = webtest.TestApp(config.make_wsgi_app())
        # Fetch a file
        response = app.get('/gen/foo.html')
        self.assertEqual(response.body, files['foo.html'])

        # Fetch a missing file
        response = app.get('/gen/foo.bar', expect_errors=True)
        self.assertEqual(response.status_code, 404)

    def test_serve_files(self):
        """ Pyramid will serve processed files """
        self._run_test({})

    def test_serve_static_files(self):
        """ Pyramid will serve processed files from a static view """
        settings = {
            'pike.static_view': 'true',
        }
        self._run_test(settings)

    def test_jinja2(self):
        """ Auto-configure jinja2 if it's present """
        settings = {}
        config = Configurator(settings=settings)
        config.include('pyramid_jinja2')
        config.include('pike')
        jinja_env = config.get_jinja2_environment()
        self.assertTrue(hasattr(jinja_env, 'pike'))


@unittest.skipIf(six.PY3 and sys.version_info[:2] < (3, 3),
                 "Flask doesn't support python 3.x lower than 3.3")
class TestFlask(BaseFileTest):

    """ Tests for flask extension """

    def _run_test(self, config):
        """ Run a simple flask app and check that serving files works """
        import flask
        app = flask.Flask(__name__)
        app.config.update(config)
        files = {
            'foo.html': b'<h1>hello world</h1>',
            'foo.js': b"alert('hello world');",
        }
        self.make_files(files)
        env = pike.flaskme(app)
        with pike.Graph('assets') as graph:
            pike.glob('.', '*')
        env.add(graph)
        env.run_all()

        client = app.test_client()
        # Fetch a file
        response = client.get('/gen/foo.html')
        self.assertEqual(response.get_data(), files['foo.html'])

        # Fetch a missing file
        response = client.get('/gen/foo.bar')
        self.assertEqual(response.status_code, 404)

    def test_serve_files(self):
        """ Flask will serve processed files """
        self._run_test({})

    def test_serve_files_abs_dir(self):
        """ Flask will serve processed files from an absolute path """
        self._run_test({
            'PIKE_OUTPUT_DIR': os.path.join(os.getcwd(), 'gen'),
        })
