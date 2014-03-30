""" Tests for pyramid extension """
import webtest
from pyramid.config import Configurator

import pike
from pike.test import BaseFileTest


class TestPyramidExtension(BaseFileTest):

    """ Tests for the pyramid extension """

    def test_serve_files(self):
        """ Pyramid will serve processed files """
        settings = {}
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

        app = webtest.TestApp(config.make_wsgi_app())
        # Fetch a file
        response = app.get('/gen/foo.html')
        self.assertEqual(response.body, files['foo.html'])

        # Fetch a missing file
        response = app.get('/gen/foo.bar', expect_errors=True)
        self.assertEqual(response.status_code, 404)

    def test_jinja2(self):
        """ Auto-configure jinja2 if it's present """
        settings = {}
        config = Configurator(settings=settings)
        config.include('pyramid_jinja2')
        config.include('pike')
        jinja_env = config.get_jinja2_environment()
        self.assertTrue(hasattr(jinja_env, 'pike'))
