# -*- coding: utf-8 -*-
from __future__ import print_function
import re
import sys

import pkg_resources


#: Matches with comment string starts with `#`.
comment_re = re.compile(r'#\s*(.+)\s*$')


PYTHON_VERSION, __, __ = sys.version.partition(' ')


# is it running on pypy?
try:
    import __pypy__
except ImportError:
    PYPY = False
else:
    PYPY = True
    del __pypy__


def installs(sysreq_string, python_version=PYTHON_VERSION, pypy=PYPY):
    for sysreq in sysreq_string.split():
        if sysreq == 'no-pypy':
            if pypy:
                return False
        elif sysreq.startswith('python'):
            if python_version not in pkg_resources.Requirement.parse(sysreq):
                return False
    return True


def fit_requirements(requirements, python_version=PYTHON_VERSION, pypy=PYPY):
    """Yields requirement lines only compatible with the current system.

    It parses comments of the given requirement lines.  A comment string can
    include python version requirement and `no-pypy` flag to skip to install on
    incompatible system:

    .. sourcecode::

       # requirements.txt
       pytest>=2.6.1
       eventlet>=0.15  # python>=2.6,<3
       gevent>=1  # python>=2.5,<3 no-pypy
       greenlet>=0.4.4  # python>=2.4
       yappi>=0.92  # python>=2.6,!=3.0 no-pypy

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
        if installs(comment, python_version, pypy):
            yield line[:match.start()].rstrip() + '\n'


if __name__ == '__main__':
    filename = sys.argv[1]
    with open(filename) as f:
        requirements = f.readlines()
    requirements = fit_requirements(requirements)
    print(''.join(requirements))
