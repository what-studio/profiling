# -*- coding: utf-8 -*-
"""
profiling
~~~~~~~~~

A profilier.

"""
from __future__ import with_statement
import re
from setuptools import setup


# detect the current version
with open('profiling/__init__.py') as f:
    version = re.search(r'__version__\s*=\s*\'(.+?)\'', f.read()).group(1)
assert version


setup(
    name='profiling',
    version=version,
    license='BSD',
    author='What! Studio',
    maintainer='Heungsub Lee',
    maintainer_email='sub@nexon.co.kr',
    platforms='linux',
    packages=['profiling', 'profiling.timers'],
    classifiers=[
        'Development Status :: 1 - Planning',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Debuggers',
    ],
    install_requires=[
        'click>=3.2',
        'gevent',
        'urwid>=1.2.1',
        'urwid-geventloop',
    ]
)
