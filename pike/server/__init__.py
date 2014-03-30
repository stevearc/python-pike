""" Adapters for web frameworks """

from pike import Environment, Graph, WriteNode, UrlNode, XargsNode


def get_environment(watch, cache_file, url_prefix, output_dir):
    """ Construct a pike environment for a webserver """
    with Graph('write-and-gen-url') as write_and_url:
        WriteNode(output_dir).connect(UrlNode(url_prefix))

    with Graph('gen-file-and-url') as default_output:
        XargsNode(write_and_url)

    env = Environment(watch=watch, cache=cache_file)
    env.set_default_output(default_output)
    return env
