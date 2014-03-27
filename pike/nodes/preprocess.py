""" Nodes that invoke preprocessors. """
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
    outputs = ('default', 'map', 'coffee')

    def __init__(self, maps=True):
        super(CoffeeNode, self).__init__()
        self.maps = maps

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
