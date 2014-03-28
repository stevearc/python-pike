"""
Pike adapter for Pyramid.

"""
from pyramid.httpexceptions import HTTPNotFound
from pyramid.response import FileResponse
from pyramid.settings import asbool

import os
from ..env import Environment, DebugEnvironment
from ..graph import Graph
from ..nodes import WriteNode, UrlNode, XargsNode


def serve_asset(request):
    """ A view that will serve generated assets """
    pieces = request.matchdict['path']
    if '..' in pieces:
        # TODO: (stevearc 2014-03-14) Do I need this? Does pyramid url routing
        # handle relative paths?
        return HTTPNotFound()
    # Don't serve files beginning with '_' or '.'
    if pieces[-1].startswith('_') or pieces[-1].startswith('.'):
        return HTTPNotFound()
    path = '/'.join(pieces)
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

    config.add_route(path, '/%s/*path' % path)
    config.add_view(serve_asset, route_name=path)

    with Graph('write-and-gen-url') as write_and_url:
        WriteNode(output_dir) | UrlNode(path)

    with Graph('gen-file-and-url') as default_output:
        XargsNode(write_and_url)

    if watch:
        cache_file = settings.get('pike.cache_file', '.pike-cache')
        env = DebugEnvironment(cache_file)
    else:
        env = Environment()
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
