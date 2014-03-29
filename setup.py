""" Setup file """
import os
import re
import sys

from setuptools import setup, find_packages


HERE = os.path.abspath(os.path.dirname(__file__))


def read(*filepath):
    """ Read the contents of a file """
    with open(os.path.join(HERE, *filepath), 'r') as ifile:
        return ifile.read()

README = read('README.rst')
# Remove custom RST extensions for pypi
CHANGES = re.sub(r'\(\s*:(issue|pr|sha):.*?\)', '', read('CHANGES.rst'))

REQUIREMENTS = [
    'six',
]

TEST_REQUIREMENTS = read('requirements_test.txt').split('\n')

if sys.version_info[:2] < (2, 7):
    TEST_REQUIREMENTS.extend(['unittest2'])

if __name__ == "__main__":
    setup(
        name='pike',
        version='0.0.0',
        description='Asset pipeline and make tool',
        long_description=README + '\n\n' + CHANGES,
        classifiers=[
            'Development Status :: 4 - Beta',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 2.6',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.2',
            'Programming Language :: Python :: 3.3',
        ],
        author='Steven Arcangeli',
        author_email='stevearc@stevearc.com',
        url='http://github.com/stevearc/pike',
        license='MIT',
        keywords='asset assets pipe pipeline make build tool',
        platforms='any',
        include_package_data=True,
        packages=find_packages(exclude=('tests',)),
        install_requires=REQUIREMENTS,
        tests_require=REQUIREMENTS + TEST_REQUIREMENTS,
    )
