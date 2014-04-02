"""
app.jinja_env.add_extension("pike.ext.JinjaExtension")

"""
import os

from flask import abort, send_from_directory

from . import get_environment, cache_file_setting
from pike.env import Environment
from pike.util import resource_spec


def configure(app):
    """ Configure a flask app to use pike """
    output_dir = app.config.get('PIKE_OUTPUT_DIR', 'gen')
    watch = app.config.get('PIKE_WATCH', True)
    url_prefix = app.config.get('PIKE_URL_PREFIX', 'gen')
    serve_files = app.config.get('PIKE_SERVE_FILES', True)
    cache_file = cache_file_setting(output_dir,
                                    app.config.get('PIKE_CACHE_FILE'))
    load_file = app.config.get('PIKE_LOAD_FILE')

    if load_file is None:
        env = get_environment(watch, cache_file, url_prefix, output_dir)
    else:
        env = Environment()
        env.load(resource_spec(load_file))
    app.jinja_env.add_extension("pike.ext.JinjaExtension")
    app.jinja_env.pike = env

    if serve_files:
        @app.route('/%s/<path:filename>' % url_prefix)
        def serve_asset(filename):
            """ A view that will serve generated assets """
            fullpath = env.lookup(filename)
            if fullpath and os.path.exists(fullpath):
                if os.path.isabs(fullpath):
                    directory, fullpath = os.path.split(fullpath)
                else:
                    directory = os.getcwd()
                return send_from_directory(directory, fullpath)
            else:
                return abort(404)
    return env
