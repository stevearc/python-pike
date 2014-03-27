""" Template extensions. """

from jinja2 import nodes
from jinja2.ext import Extension


class JinjaExtension(Extension):

    """
    Extension for jinja2.

    Examples
    --------
    ::

        {% pike 'pipe.coffee' %}
            <link rel="stylesheet" type="text/css" href="{{ ASSET.url }}">
        {% endpike %}

    """

    tags = set(['pike'])

    def __init__(self, environment):
        super(JinjaExtension, self).__init__(environment)
        environment.extend(
            pike=None,
        )

    def parse(self, parser):
        # the first token is the token that started the tag.  In our case
        # we only listen to ``'pike'`` so this will be a name token with
        # `pike` as value.  We get the line number so that we can give
        # that line number to the nodes we create by hand.
        lineno = parser.stream.next().lineno

        # now we parse a single expression that is used as the pipe identifier
        args = [parser.parse_expression()]

        # now we parse the body of the cache block up to `endpike` and
        # drop the needle (which would always be `endpike` in that case)
        body = parser.parse_statements(['name:endpike'], drop_needle=True)

        call_args = [nodes.Name('ASSET', 'store')]

        return nodes.CallBlock(self.call_method('_run_pipe', args), call_args,
                               [], body).set_lineno(lineno)

    def _run_pipe(self, name, caller=None):
        """ Run a pipeline and render the tag contents for each output """
        if ':' in name:
            name, key = name.split(':', 1)
        else:
            key = 'default'
        env = self.environment.pike
        if env is None:
            raise RuntimeError('Pike not found')
        try:
            return u''.join([caller(data) for data in env.run(name)[key]])
        except KeyError:
            return u''
