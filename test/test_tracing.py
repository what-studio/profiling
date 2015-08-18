# -*- coding: utf-8 -*-
import sys

import pytest
import six

from profiling.stats import FrozenStatistic, RecordingStatistic
from profiling.tracing import TracingProfiler
from utils import factorial, find_stat, foo


if six.PY3:
    map = lambda *x: list(six.moves.map(*x))


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
    stat1 = find_stat(profiler.stats, 'foo')
    stat2 = find_stat(profiler.stats, 'bar')
    stat3 = find_stat(profiler.stats, 'baz')
    assert stat1.own_count == 0
    assert stat2.own_count == 0
    assert stat3.own_count == 1
    assert stat1.deep_count == 1
    assert stat2.deep_count == 1
    assert stat3.deep_count == 1


def test_profiler():
    profiler = TracingProfiler(top_frame=sys._getframe())
    assert isinstance(profiler.stats, RecordingStatistic)
    stats, cpu_time, wall_time = profiler.result()
    assert isinstance(stats, FrozenStatistic)
    assert len(stats) == 0
    with profiler:
        factorial(1000)
        factorial(10000)
    stat1 = find_stat(profiler.stats, 'factorial')
    stat2 = find_stat(profiler.stats, '__enter__')
    stat3 = find_stat(profiler.stats, '__exit__')
    assert stat1.deep_time != 0
    assert stat1.deep_time == stat1.own_time
    assert stat1.own_time > stat2.own_time
    assert stat1.own_time > stat3.own_time
    assert stat1.own_count == 2
    assert stat2.own_count == 0  # entering to __enter__() wasn't profiled.
    assert stat3.own_count == 1
