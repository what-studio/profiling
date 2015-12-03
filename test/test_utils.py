# -*- coding: utf-8 -*-
from collections import deque

import pytest
import six

from _utils import baz, foo, mock_code_names
from profiling.utils import frame_stack, lazy_import, repr_frame, Runnable


def test_runnable():
    # not implemented.
    runnable = Runnable()
    with pytest.raises(NotImplementedError):
        runnable.start()
    # implemented well.
    class Implementation(Runnable):
        step = 1
        def run(self):
            self.step = 2
            yield
            self.step = 3
    runnable = Implementation()
    assert runnable.step == 1
    assert not runnable.is_running()
    runnable.start()
    assert runnable.step == 2
    assert runnable.is_running()
    with pytest.raises(RuntimeError):
        runnable.start()
    runnable.stop()
    assert runnable.step == 3
    assert not runnable.is_running()
    with pytest.raises(RuntimeError):
        runnable.stop()
    # implemented not well.
    class NotYield(Runnable):
        def run(self):
            if False:
                yield
    runnable = NotYield()
    with pytest.raises(TypeError):
        runnable.start()
    class YieldSomething(Runnable):
        def run(self):
            yield 123
    runnable = YieldSomething()
    with pytest.raises(TypeError):
        runnable.start()
    class YieldTwice(Runnable):
        def run(self):
            yield
            yield
    runnable = YieldTwice()
    runnable.start()
    with pytest.raises(TypeError):
        runnable.stop()


def test_frame_stack():
    def to_code_names(frames):
        code_names = deque()
        for frame in reversed(frames):
            code_name = frame.f_code.co_name
            if code_name not in mock_code_names:
                break
            code_names.appendleft(code_name)
        return list(code_names)
    baz_frame = foo()
    foo_frame = baz_frame.f_back.f_back
    frames = frame_stack(baz_frame)
    assert to_code_names(frames) == ['foo', 'bar', 'baz']
    # base frame.
    frames = frame_stack(baz_frame, base_frame=foo_frame)
    assert to_code_names(frames) == ['bar', 'baz']
    # ignored codes.
    frames = frame_stack(baz_frame, ignored_codes=[
        six.get_function_code(foo),
        six.get_function_code(baz),
    ])
    assert to_code_names(frames) == ['bar']


def test_lazy_import():
    class O(object):
        math = lazy_import('math')
    assert O.math is __import__('math')


def test_repr_frame():
    frame = foo()
    assert repr_frame(frame) == '<string>:9'
    assert repr_frame(frame.f_back) == '<string>:6'
