#!/usr/bin/env python
""" Script to watch for changes and re-run tests """
import os
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
        try:
            self.session = subprocess.check_output(['tmux', 'display-message',
                                                    '-p', '#S']).strip()
            subprocess.call(['tmux', 'rename-window', 'tests'])
            self.window_name = 'tests'
        except (subprocess.CalledProcessError, os.error):
            self.session = None

    def process(self, *_):
        if self.cover:
            proc = subprocess.call(['coverage', 'run', '--branch',
                                    '--source=pike', 'setup.py', 'nosetests'])
            subprocess.call(['coverage', 'html'])
        else:
            proc = subprocess.call(['python', 'setup.py', 'nosetests'])
        if self.session is not None:
            status = '^_^' if proc == 0 else 'X_X'
            next_name = 'tests %s' % status
            subprocess.call(['tmux', 'rename-window', '-t', '%s:%s' % (self.session, self.window_name), next_name])
            self.window_name = next_name
        return []


def main():
    """ Run graph forever """
    logging.basicConfig()
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('-c', '--coverage', action='store_true',
                        help="Collect coverage information")
    args = parser.parse_args()

    env = pike.Environment(watch=True, cache='.pike-cache', throttle=1)
    with pike.Graph('tests') as graph:
        runner = TestRunnerNode(args.coverage)
        pike.glob('pike', '*.py') | runner
    env.add(graph)
    env.run_forever()

if __name__ == '__main__':
    main()
