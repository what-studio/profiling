# -*- coding: utf-8 -*-
from collections import deque
import sys
from textwrap import dedent

import pytest
import six

from profiling.profiler import Profiler
from profiling.stats import FrozenStatistics, RecordingStatistics
from utils import factorial, find_stat, profiling


if six.PY3:
    map = lambda *x: list(six.moves.map(*x))


foo = None  # placeheolder
mock_code_names = ['foo', 'bar', 'baz']
for name, next_name in zip(mock_code_names[:-1], mock_code_names[1:]):
    exec(dedent('''
    def {0}():
        return {1}()
    ''').format(name, next_name))
exec('def {0}(): return sys._getframe()'.format(mock_code_names[-1]))


def test_frame_stack():
    def to_code_names(frames):
        code_names = deque()
        for frame in reversed(frames):
            code_name = frame.f_code.co_name
            if code_name not in mock_code_names:
                break
            code_names.appendleft(code_name)
        return list(code_names)
    profiler = Profiler()
    frame = foo()
    frame_stack = profiler._frame_stack(frame)
    assert to_code_names(frame_stack) == ['foo', 'bar', 'baz']
    # top frame
    profiler = Profiler(top_frame=frame.f_back)
    frame_stack = profiler._frame_stack(frame)
    assert to_code_names(frame_stack) == ['bar', 'baz']
    # top code
    profiler = Profiler(top_code=frame.f_back.f_code)
    frame_stack = profiler._frame_stack(frame)
    assert to_code_names(frame_stack) == ['bar', 'baz']
    # both of top frame and top code
    profiler = Profiler(top_frame=frame.f_back, top_code=frame.f_back.f_code)
    frame_stack = profiler._frame_stack(frame)
    assert to_code_names(frame_stack) == ['bar', 'baz']


def test_setprofile():
    profiler = Profiler()
    assert sys.getprofile() is None
    profiler.start()
    assert sys.getprofile() == profiler._profile
    profiler.stop()
    assert sys.getprofile() is None
    sys.setprofile(lambda *x: x)
    with pytest.raises(RuntimeError):
        profiler.start()
    sys.setprofile(None)


def test_profile():
    profiler = Profiler()
    frame = foo()
    profiler._profile(frame, 'call', None)
    profiler._profile(frame, 'return', None)
    assert len(profiler.stats) == 1
    stat1 = find_stat(profiler.stats, 'foo')
    stat2 = find_stat(profiler.stats, 'bar')
    stat3 = find_stat(profiler.stats, 'baz')
    assert stat1.own_calls == 0
    assert stat2.own_calls == 0
    assert stat3.own_calls == 1
    assert stat1.total_calls == 1
    assert stat2.total_calls == 1
    assert stat3.total_calls == 1


def test_profiler():
    profiler = Profiler(top_frame=sys._getframe())
    assert isinstance(profiler.stats, RecordingStatistics)
    assert isinstance(profiler.result(), FrozenStatistics)
    assert len(profiler.stats) == 0
    with profiling(profiler):
        factorial(1000)
        factorial(10000)
    stat1 = find_stat(profiler.stats, 'factorial')
    stat2 = find_stat(profiler.stats, '__enter__')
    stat3 = find_stat(profiler.stats, '__exit__')
    assert stat1.total_time != 0
    assert stat1.total_time == stat1.own_time
    assert stat1.own_time > stat2.own_time
    assert stat1.own_time > stat3.own_time
    assert stat1.own_calls == 2
    assert stat2.own_calls == 0  # entering to __enter__() wasn't profiled.
    assert stat3.own_calls == 1
