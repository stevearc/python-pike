.. _deploying:

Deploying to Production
=======================

Serving Files with a Real Server™
---------------------------------
Serving static files is much more efficient if you use Apache or nginx instead
of your python web framework. The following settings are important:

* **serve_files** - ``False``
* **output_dir** - Make this directory accessible for your server
* **watch** - ``False``. Don't watch for changes on production servers.
* **cache_file** - ``None``. Use in-memory cache. It's faster than SQLite.
* **url_prefix** - The particular value doesn't much matter, but it should include a version number to properly bust caches.

Instead of using :meth:`~pike.env.Environment.run_forever` you should just call
:meth:`~pike.env.Environment.run_all` to compile the assets once.

Serving Files with a CDN
------------------------
If you are using a CDN, then your files may not even be packaged with your web
application.

1. Build the assets with the CDN settings
2. Upload the assets to your CDN
3. Save the asset metadata to a file (:meth:`pike.env.Environment.save`)
4. Distribute the file with your web application and use the **load_file** setting

Also note that the **url_prefix** will probably look something like
``//my.cdn.com/<version>``.

Example Application
-------------------
This is an example pyramid application to demonstrate how you could construct
the code for local development and CDN deployment.

**__init__.py**

.. code-block:: python

    from pyramid.config import Configurator
    from pyramid.settings import asbool
    from .assets import configure_env

    def main(config, **settings):
        debug = asbool(settings.get(__package__ + '.debug', False))
        config = Configurator(settings=settings)
        config.include('pyramid_jinja2')
        config.include('pike')
        env = config.get_pike_env()
        if debug:
            configure_env(env, debug=True)
            env.run_forever(daemon=True)
        return config.make_wsgi_app()

**assets.py**

.. code-block:: python

    def configure_env(env, debug):
        asset_dir = __package__ + ':static'

        # lib js
        with pike.Graph('lib.js') as graph:
            n = pike.glob(asset_dir, '*.js', 'lib')
            if not debug:
                n | pike.concat('lib.js')
        env.add(graph)


        # lib css
        with pike.Graph('lib.css') as graph:
            n = pike.glob(asset_dir, '*.css', 'lib')
            if not debug:
                n | pike.concat('lib.css')
        env.add(graph)


        # app less
        with pike.Graph('app.less') as graph:
            n = pike.glob(asset_dir, '*.less', 'app') | pike.less()
            if not debug:
                n | pike.concat('app.css')
        env.add(graph, partial=True)

        # app coffeescript
        with pike.Graph('app.coffee') as graph:
            p = pike.glob(asset_dir, '*.coffee', 'app') | pike.coffee()
            if not debug:
                p | pike.concat('app.js')
        env.add(graph, partial=True)

    def main():
        cdn_prefix = '//my.cdn.com'

        with pike.Graph('write-and-gen-url') as write_and_url:
            pike.write('cdn_files') | pike.url(cdn_prefix)

        with Graph('gen-file-and-url') as default_output:
            pike.xargs(write_and_url)

        env = pike.Environment()
        env.set_default_output(default_output)
        configure_env(env, debug=False)
        env.run_all()
        env.save('production_asset_list.p')

    if __name__ == '__main__':
        main()

While in a development environment, the ``__package__ + '.debug'``
setting will be set to ``True``. To prepare for deploy, you can just
run the **assets.py** file and upload the contents of ``cdn_files``.
Distribute the generated ``production_asset_list.p`` file with your
updated application, and point to it with the **pike.load_file**
setting.
