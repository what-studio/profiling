# -*- coding: utf-8 -*-
from __future__ import print_function
import re
import sys

import pkg_resources


#: Matches with comment string starts with `#`.
comment_re = re.compile(r'#\s*(.+)\s*$')


# is it running on pypy?
try:
    import __pypy__
except ImportError:
    PYPY = False
else:
    PYPY = True
    del __pypy__


def installs(req_string, python_version=sys.version, pypy=PYPY):
    for seg in req_string.split():
        if seg == 'no-pypy' and pypy:
            return False
        elif seg.startswith('python'):
            req = pkg_resources.Requirement.parse(seg)
            if python_version not in req:
                return False
        else:
            assert False
    return True


def filter_requirements(requirements, python_version=sys.version, pypy=PYPY):
    for line in requirements:
        match = comment_re.search(line)
        if match is None:
            yield line
            continue
        comment = match.group(1)
        if installs(comment, python_version, pypy):
            yield line[:match.start()].rstrip()


if __name__ == '__main__':
    filename = sys.argv[1]
    with open(filename) as f:
        requirements = f.readlines()
    requirements = filter_requirements(requirements)
    print(''.join(requirements))
