#!/usr/bin/env python
""" Script to watch for changes and rebuild docs """
import os
import argparse
import logging
import subprocess

import pike


class DocBuilderNode(pike.Node):

    """ Build the docs when triggered """

    name = 'doc_builder'

    def __init__(self):
        super(DocBuilderNode, self).__init__()

    def process(self, *_):
        subprocess.call(['make', 'html'], cwd='doc')
        return []


def main():
    """ Run graph forever """
    env = pike.Environment(watch=True, cache='.pike-cache')
    with pike.Graph('docs') as graph:
        builder = DocBuilderNode()
        pike.glob('doc', '*.rst') | builder
        pike.glob('pike', '*.py') | builder
    env.add(graph)
    env.run_forever(sleep=1)

if __name__ == '__main__':
    main()
