# -*- coding: utf-8 -*-
import sys

import pytest
import six

from profiling.profiler import Profiler
from profiling.mock import mock_code, mock_stacked_frame
from profiling.stats import FrozenStatistics, RecordingStatistics
from utils import factorial, find_stat, profiling


if six.PY3:
    map = lambda *x: list(six.moves.map(*x))


def test_frame_stack():
    def to_code_names(frames):
        return [f.f_code.co_name for f in frames]
    profiler = Profiler()
    frame = mock_stacked_frame(map(mock_code, ['foo', 'bar', 'baz']))
    frame_stack = profiler._frame_stack(frame)
    assert to_code_names(frame_stack) == ['baz', 'bar', 'foo']
    # top frame
    profiler = Profiler(top_frame=frame.f_back)
    frame_stack = profiler._frame_stack(frame)
    assert to_code_names(frame_stack) == ['bar', 'foo']
    # top code
    profiler = Profiler(top_code=frame.f_back.f_code)
    frame_stack = profiler._frame_stack(frame)
    assert to_code_names(frame_stack) == ['bar', 'foo']
    # both of top frame and top code
    profiler = Profiler(top_frame=frame.f_back, top_code=frame.f_back.f_code)
    frame_stack = profiler._frame_stack(frame)
    assert to_code_names(frame_stack) == ['bar', 'foo']


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
    frame = mock_stacked_frame(map(mock_code, ['foo', 'bar', 'baz']))
    profiler._profile(frame, 'call', None)
    profiler._profile(frame, 'return', None)
    assert len(profiler.stats) == 1
    stat1 = find_stat(profiler.stats, 'baz')
    stat2 = find_stat(profiler.stats, 'bar')
    stat3 = find_stat(profiler.stats, 'foo')
    assert stat1.calls == 0
    assert stat2.calls == 0
    assert stat3.calls == 1


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
    assert stat1.calls == 2
    assert stat2.calls == 0  # entering to __enter__() wasn't profiled.
    assert stat3.calls == 1
