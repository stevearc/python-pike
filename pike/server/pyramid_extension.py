"""
Pike extension for Pyramid.

"""
import os

from pyramid.httpexceptions import HTTPNotFound
from pyramid.response import FileResponse
from pyramid.settings import asbool

from pike import Environment, Graph, WriteNode, UrlNode, XargsNode


def serve_asset(request):
    """ A view that will serve generated assets """
    path = '/'.join(request.matchdict['path'])
    fullpath = request.registry.pike_env.lookup(path)
    if fullpath and os.path.exists(fullpath):
        return FileResponse(fullpath, request=request, cache_max_age=31556926)
    else:
        return HTTPNotFound()


def includeme(config):
    """ Set up pyramid app with pike """
    settings = config.get_settings()

    output_dir = settings.get('pike.output_dir', 'gen')
    watch = asbool(settings.get('pike.watch', True))
    path = settings.get('pike.url_prefix', 'gen').strip('/')
    serve_files = asbool(settings.get('pike.serve_files', True))

    if serve_files:
        config.add_route('pike_assets', '/%s/*path' % path)
        config.add_view(serve_asset, route_name='pike_assets')

    with Graph('write-and-gen-url') as write_and_url:
        WriteNode(output_dir).connect(UrlNode(path))

    with Graph('gen-file-and-url') as default_output:
        XargsNode(write_and_url)

    cache_file = settings.get('pike.cache_file', '.pike-cache')
    env = Environment(watch=watch, cache=cache_file)
    env.set_default_output(default_output)
    config.registry.pike_env = env
    config.add_directive('get_pike_env', lambda c: c.registry.pike_env)

    # If pyramid_jinja2 has already been included, take care of the
    # configuration automatically
    try:
        config.add_jinja2_extension('pike.ext.JinjaExtension')
        config.get_jinja2_environment().pike = env
    except AttributeError:
        pass
