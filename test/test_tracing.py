# -*- coding: utf-8 -*-
import sys

import pytest

from _utils import factorial, find_stats, foo
from profiling.stats import RecordingStatistics
from profiling.tracing import TracingProfiler


def test_setprofile():
    profiler = TracingProfiler()
    assert sys.getprofile() is None
    with profiler:
        assert sys.getprofile() == profiler._profile
    assert sys.getprofile() is None
    sys.setprofile(lambda *x: x)
    with pytest.raises(RuntimeError):
        profiler.start()
    sys.setprofile(None)


def test_profile():
    profiler = TracingProfiler()
    frame = foo()
    profiler._profile(frame, 'call', None)
    profiler._profile(frame, 'return', None)
    assert len(profiler.stats) == 1
    stats1 = find_stats(profiler.stats, 'foo')
    stats2 = find_stats(profiler.stats, 'bar')
    stats3 = find_stats(profiler.stats, 'baz')
    assert stats1.own_hits == 0
    assert stats2.own_hits == 0
    assert stats3.own_hits == 1
    assert stats1.deep_hits == 1
    assert stats2.deep_hits == 1
    assert stats3.deep_hits == 1


def test_profiler():
    profiler = TracingProfiler(base_frame=sys._getframe())
    assert isinstance(profiler.stats, RecordingStatistics)
    stats, cpu_time, wall_time = profiler.result()
    assert len(stats) == 0
    with profiler:
        factorial(1000)
        factorial(10000)
    stats1 = find_stats(profiler.stats, 'factorial')
    stats2 = find_stats(profiler.stats, '__enter__')
    stats3 = find_stats(profiler.stats, '__exit__')
    assert stats1.deep_time != 0
    assert stats1.deep_time == stats1.own_time
    assert stats1.own_time > stats2.own_time
    assert stats1.own_time > stats3.own_time
    assert stats1.own_hits == 2
    assert stats2.own_hits == 0  # entering to __enter__() wasn't profiled.
    assert stats3.own_hits == 1
