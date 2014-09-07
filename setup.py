# -*- coding: utf-8 -*-
"""
profiling
~~~~~~~~~

An interactive profilier.

"""
from __future__ import with_statement
import ast
from setuptools import setup
from setuptools.command.test import test
import subprocess


def get_version(filename):
    """Detects the current version."""
    with open(filename) as f:
        tree = ast.parse(f.read(), filename)
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, = node.targets
            if isinstance(target, ast.Name) and target.id == '__version__':
                return node.value.s
    raise ValueError('__version__ not found from {0}'.format(filename))


def requirements(filename):
    """Reads requirements from a file."""
    with open(filename) as f:
        return [x.strip() for x in f.readlines() if x.strip()]


# use pytest instead.
def run_tests(self):
    raise SystemExit(subprocess.call(['py.test', '-v']))
test.run_tests = run_tests


setup(
    name='profiling',
    version=get_version('profiling/__init__.py'),
    license='BSD',
    author='What! Studio',
    maintainer='Heungsub Lee',
    maintainer_email='sub@nexon.co.kr',
    platforms='linux',
    packages=['profiling', 'profiling.remote', 'profiling.timers'],
    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Debuggers',
    ],
    install_requires=requirements('requirements.txt'),
    tests_require=requirements('test/requirements.txt'),
    test_suite='',
)
