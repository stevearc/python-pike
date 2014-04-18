""" Nodes that invoke preprocessors. """
import posixpath
import re
import os

from .base import Node
from pike.items import FileMeta, FileDataBlob
from pike.util import run_cmd, tempd


class CoffeeNode(Node):

    """
    Run the Coffeescript compiler.

    Requires coffeescript to be installed (npm install -g coffee-script)

    Parameters
    ----------
    maps : bool
        If True, will produce two named outputs in addition to the compiled
        javascript: 'map' which will contain the map files, and 'coffee' which
        will contain the original coffeescript files. (default True)

    """
    name = 'coffee'

    def __init__(self, maps=True):
        super(CoffeeNode, self).__init__()
        self.maps = maps
        if maps:
            self.outputs = ('default', 'map', 'coffee')

    def process(self, stream):
        if self.maps:
            maps = []
            js_files = []
            coffee = []
            with tempd() as tmp:
                for item in stream:
                    fullpath = os.path.join(tmp, item.filename)
                    root, filename = os.path.split(fullpath)

                    cmd = ['coffee', '-c', '-m', filename]
                    item.data.as_file(fullpath)
                    run_cmd(cmd, cwd=root)

                    coffee.append(item)

                    js_item = FileMeta(item.filename, item.path)
                    js_item.setext('.js')
                    with open(os.path.join(tmp, js_item.filename), 'r') as ifile:
                        js_item.data = FileDataBlob(ifile.read())
                    js_files.append(js_item)

                    mapfile = FileMeta(item.filename, item.path)
                    mapfile.setext('.map')
                    with open(os.path.join(tmp, mapfile.filename), 'r') as ifile:
                        mapfile.data = FileDataBlob(ifile.read())
                    maps.append(mapfile)
            return {
                'default': js_files,
                'map': maps,
                'coffee': coffee,
            }
        else:
            ret = []
            cmd = ['coffee', '-p', '-s']
            for item in stream:
                item.data = FileDataBlob(run_cmd(cmd, item.data.read()))
                item.setext('.js')
                ret.append(item)
            return ret

    def process_one(self, item):
        if self.maps:
            item.data.as_file(item.filename)
            cmd = ['coffee', '-m', item.filename]

        else:
            cmd = ['coffee', '-p', '-s']
            item.data = FileDataBlob(run_cmd(cmd, item.data.read()))
        item.setext('.js')
        return item


class LessNode(Node):

    """
    Run the LESS CSS compiler.

    Requires less to be installed (npm install -g less)

    """
    name = 'less'

    def process_one(self, item):
        cmd = ['lessc', '-']
        path = os.path.dirname(item.fullpath)
        item.data = FileDataBlob(run_cmd(cmd, item.data.read(), cwd=path))
        item.setext('.css')
        return item


class UglifyNode(Node):

    """
    Run Uglifyjs

    Requires uglify to be installed (npm install -g uglify-js)

    """
    name = 'uglifyjs'

    def process_one(self, item):
        cmd = ['uglifyjs', '-']
        path = os.path.dirname(item.fullpath)
        item.data = FileDataBlob(run_cmd(cmd, item.data.read(), cwd=path))
        return item


class CleanCssNode(Node):
    """
    Run cleancss

    Requires clean-css to be installed (npm install -g clean-css)

    """

    def process_one(self, item):
        path = os.path.dirname(item.fullpath)
        cmd = ['cleancss', '--root', path]
        item.data = FileDataBlob(run_cmd(cmd, item.data.read(), cwd=path))
        return item


class RewriteCssNode(Node):
    """
    Rewrites css urls

    """
    def __init__(self, prefix='', absolute=True):
        super(RewriteCssNode, self).__init__()
        self.prefix = prefix.strip('/')
        if self.prefix:
            self.prefix += '/'
        self.absolute = absolute

    def process_one(self, item):
        pattern = r"url\('([^']*/)?(.*?)'\)"
        if self.absolute:
            output = []
            cursor_pos = 0
            data = item.data.read()
            filepath = posixpath.split(item.filename)[0]
            for match in re.finditer(pattern, data, re.M | re.S):
                path = match.group(1)
                newpath = posixpath.join(filepath, path, match.group(2))
                fullpath = posixpath.normpath(newpath)
                output.append(data[cursor_pos:match.start()])
                output.append("url('%s')" % fullpath)
                cursor_pos = match.end()
            output.append(data[cursor_pos:])
            text = ''.join(output)
        else:
            replace = r"url('%s\2')" % self.prefix
            text = re.sub(pattern, replace, item.data.read(), re.M | re.S)
        item.data = FileDataBlob(text)
        return item
