.. _web_frameworks:

Integration with Web Frameworks
===============================

Pyramid
-------
You can add pike to your application by including it
(``config.include('pike')`` or putting it in your ``pyramid.includes``). If you
are using ``pyramid_jinja2``, you should include pike *afterwards* so that pike
can automatically set up and configure the :ref:`jinja2 extension <jinja2>`.

To add graphs to the pike environment, pull the env off of the config object
and go nuts:

.. code-block:: python

    config.include('pike')
    env = config.get_pike_env()
    with pike.Graph('lib.js') as graph:
        pike.glob('lib', '*.js')
    env.add(graph)

Settings
^^^^^^^^

pike.output_dir
~~~~~~~~~~~~~~~
**Argument:** str, optional

The directory to write resources to. Default ``'gen'``. This may be a file path or
a package specification (e.g. ``'mypackage:images/'``)

pike.watch
~~~~~~~~~~
**Argument:** bool, optional

If True, will watch source files for changes. Default ``True``.

pike.url_prefix
~~~~~~~~~~~~~~~
**Argument:** str, optional

Prefix all generated file urls with this string. Default ``'gen/'``.

pike.static_view
~~~~~~~~~~~~~~~~
**Argument:** bool, optional

If True, will serve the files by registering a pyramid static view to the
output directory. Default ``False``.

pike.serve_files
~~~~~~~~~~~~~~~~
**Argument:** bool, optional

If False, pyramid will not serve the generated files. You will need to set up a
web server (nginx, Apache, etc) to serve the files for you. Default ``True``.

pike.cache_file
~~~~~~~~~~~~~~~
**Argument:** str, optional

The name of the file where pike will cache its data. Default will be
``'.pike-cache'`` inside of ``pike.output_dir``.

Flask
-----
You can enable pike from your flask app by making a call to
:meth:`pike.flaskme`. This will create an Environment, set up the
:ref:`jinja2 extension <jinja2>`, and optionally create an endpoint to
serve the generated files.

.. code-block:: python

    app = Flask(__name__)
    env pike.flaskme(app)
    with pike.Graph('lib.js') as graph:
        pike.glob('lib', '*.js')
    env.add(graph)

You may configure the behavior of :meth:`~pike.flaskme` with variables
in your ``app.config``.

Settings
^^^^^^^^

PIKE_OUTPUT_DIR
~~~~~~~~~~~~~~~
**Argument:** str, optional

The directory to write resources to. Default ``'gen'``. This may be a
file path or a package specification (e.g. ``'mypackage:images/'``)

PIKE_WATCH
~~~~~~~~~~
**Argument:** bool, optional

If True, will watch source files for changes. Default ``True``.

PIKE_URL_PREFIX
~~~~~~~~~~~~~~~
**Argument:** str, optional

Prefix all generated file urls with this string. Default ``'gen/'``.

PIKE_SERVE_FILES
~~~~~~~~~~~~~~~~
**Argument:** bool, optional

If False, flask will not serve the generated files. You will need to set up a
web server (nginx, Apache, etc) to serve the files for you. You could also use
the flask static directory as the ``PIKE_OUTPUT_DIR``. Default ``True``.

PIKE_CACHE_FILE
~~~~~~~~~~~~~~~
**Argument:** str, optional

The name of the file where pike will cache its data. Default will be
``'.pike-cache'`` inside of ``PIKE_OUTPUT_DIR``.

Django
------
.. todo::
    Django integration

.. todo::
    Django documentation

Django integration is coming.