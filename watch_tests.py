#!/usr/bin/env python
""" Script to watch for changes and re-run tests """
import argparse
import logging
import subprocess

import pike


class TestRunnerNode(pike.Node):

    """ Run the tests when triggered """

    name = 'test_runner'

    def __init__(self, cover=False):
        super(TestRunnerNode, self).__init__()
        self.cover = cover

    def process(self, *_):
        if self.cover:
            subprocess.call(['coverage', 'run', '--branch', '--source=pike',
                             'setup.py', 'nosetests'])
            subprocess.call(['coverage', 'html'])
        else:
            subprocess.call(['python', 'setup.py', 'nosetests'])
        return []


def main():
    """ Run graph forever """
    logging.basicConfig()
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('-c', '--coverage', action='store_true',
                        help="Collect coverage information")
    args = parser.parse_args()

    env = pike.DebugEnvironment()
    with pike.Graph('tests') as graph:
        runner = TestRunnerNode(args.coverage)
        pike.glob('pike', '*.py') | runner
        pike.glob('tests', '*.py') | runner
    env.add(graph)
    env.run_forever(sleep=1)

if __name__ == '__main__':
    main()
