""" Adapters for web frameworks """
import os

from pike import Environment, Graph, WriteNode, UrlNode, XargsNode
from pike.util import resource_spec


def get_environment(watch, cache_file, url_prefix, output_dir):
    """ Construct a pike environment for a webserver """
    with Graph('write-and-gen-url') as write_and_url:
        WriteNode(output_dir).connect(UrlNode(url_prefix))

    with Graph('gen-file-and-url') as default_output:
        XargsNode(write_and_url)

    env = Environment(watch=watch, cache=cache_file)
    env.set_default_output(default_output)
    return env


def cache_file_setting(output_dir, cache_file):
    """ Convenience method for converting the cache_file setting """
    if cache_file is None:
        return os.path.join(resource_spec(output_dir), '.pike-cache')
    else:
        trimmed = cache_file.strip().lower()
        if trimmed == 'none':
            return None
        else:
            return resource_spec(cache_file)
