# -*- coding: utf-8 -*-
from __future__ import print_function

import re
import sys

import pkg_resources


#: Matches with comment string starts with `#`.
comment_re = re.compile(r'#\s*(.+)\s*$')


# Detect the Python and PyPy versions.
PYTHON_VERSION = '{0}.{1}.{2}'.format(*sys.version_info)
try:
    PYPY_VERSION = '{0}.{1}.{2}'.format(*sys.pypy_version_info)
except AttributeError:
    PYPY_VERSION = None


def installs(sysreq_string,
             python_version=PYTHON_VERSION, pypy_version=PYPY_VERSION):
    for sysreq in sysreq_string.split():
        if sysreq == '!pypy' and pypy_version is not None:
            return False
        if sysreq.startswith('python'):
            if python_version not in pkg_resources.Requirement.parse(sysreq):
                return False
        elif sysreq.startswith('pypy'):
            if pypy_version is None:
                return False
            elif pypy_version not in pkg_resources.Requirement.parse(sysreq):
                return False
    return True


def fit_requirements(requirements,
                     python_version=PYTHON_VERSION, pypy_version=PYPY_VERSION):
    """Yields requirement lines only compatible with the current system.

    It parses comments of the given requirement lines.  A comment string can
    include python version requirement and `!pypy` flag to skip to install on
    incompatible system:

    .. sourcecode::

       # requirements.txt
       pytest>=2.6.1
       eventlet>=0.15  # python>=2.6,<3
       gevent>=1  # python>=2.5,<3 !pypy
       gevent==1.1rc1  # pypy<2.6.1
       greenlet>=0.4.4  # python>=2.4
       yappi>=0.92  # python>=2.6,!=3.0 !pypy

    .. sourcecode:: console

       $ pypy3.4 fit_requirements.py requirements.txt
       pytest>=2.6.1
       greenlet>=0.4.4

    """
    for line in requirements:
        match = comment_re.search(line)
        if match is None:
            yield line
            continue
        comment = match.group(1)
        if installs(comment, python_version, pypy_version):
            yield line[:match.start()].rstrip() + '\n'


if __name__ == '__main__':
    filename = sys.argv[1]
    with open(filename) as f:
        requirements = f.readlines()
    requirements = fit_requirements(requirements)
    print(''.join(requirements))
