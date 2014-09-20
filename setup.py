# -*- coding: utf-8 -*-
"""
profiling
~~~~~~~~~

An interactive profilier.

"""
from __future__ import with_statement
import ast
from setuptools import setup


def get_version(filename):
    """detect the current version."""
    with open(filename) as f:
        tree = ast.parse(f.read(), filename)
    for node in tree.body:
        if isinstance(node, ast.Assign) and \
           len(node.targets) == 1:
            target, = node.targets
            if isinstance(target, ast.Name) and target.id == '__version__':
                return node.value.s


version = get_version('profiling/__init__.py')
assert version


setup(
    name='profiling',
    version=version,
    license='BSD',
    author='What! Studio',
    maintainer='Heungsub Lee',
    maintainer_email='sub@nexon.co.kr',
    platforms='linux',
    packages=['profiling', 'profiling.remote', 'profiling.timers'],
    classifiers=[
        'Development Status :: 1 - Planning',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Debuggers',
    ],
    install_requires=[
        'click>=3.3',
        'six>=1.8.0',
        'urwid>=1.2.1',
    ],
    tests_require=[
        'pytest>=2.6.1',
        'yappi>=0.92',
    ],
)
