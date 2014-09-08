# -*- coding: utf-8 -*-
"""
    profiling.mocking
    ~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
import functools
import types

from six import PY3


__all__ = ['mock_code', 'mock_frame', 'mock_stacked_frame']


_py2_code_args = (0, 0, 0, 0, b'', (), (), (), '')
if PY3:
    _mock_code = functools.partial(types.CodeType, 0, *_py2_code_args)
else:
    _mock_code = functools.partial(types.CodeType, *_py2_code_args)
del _py2_code_args


def mock_code(name):
    """Makes a fake code object by name for built-in functions."""
    return _mock_code(name, 0, b'')


class mock_frame(object):
    """Makes a fake frame object by the given code."""

    f_code = None
    f_back = None

    def __init__(self, code, back=None):
        self.f_code = code
        self.f_back = back


def mock_stacked_frame(codes):
    """Makes a fake frame object which has own frame stack."""
    frame = None
    for code in codes[::-1]:
        frame = mock_frame(code, frame)
    return frame
