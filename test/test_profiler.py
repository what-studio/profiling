# -*- coding: utf-8 -*-
from contextlib import contextmanager
import sys

import pytest

from profiling.profiler import Profiler
from profiling.stats import FrozenStatistics, RecordingStatistics


@contextmanager
def profiling(profiler):
    try:
        profiler.start()
        yield
    finally:
        profiler.stop()


def find_stats(stats, name, _found=None, _on_found=None):
    if _found is None:
        _found = []
    for stat in stats:
        if stat.name == name:
            _found.append(stat)
            if callable(_on_found):
                _on_found(_found)
        find_stats(stat, name, _found)
    return _found


def find_stat(stats, name):
    def _on_found(found):
        raise StopIteration
    return find_stats(stats, name)[0]


def factorial(n):
    f = 1
    while n:
        f *= n
        n -= 1
    return f


def test_frame_stack():
    profiler = Profiler()
    frame = sys._getframe()
    frame_stack = profiler._frame_stack(frame)
    assert frame_stack[-1] is frame
    assert frame_stack[-2] is frame.f_back
    assert frame_stack[-3] is frame.f_back.f_back
    # top frame
    profiler = Profiler(top_frame=frame.f_back)
    frame_stack = profiler._frame_stack(frame)
    assert list(frame_stack) == [frame.f_back, frame]
    # top code
    profiler = Profiler(top_code=frame.f_back.f_code)
    frame_stack = profiler._frame_stack(frame)
    assert list(frame_stack) == [frame.f_back, frame]
    # both of top frame and top code
    profiler = Profiler(top_frame=frame.f_back, top_code=frame.f_back.f_code)
    frame_stack = profiler._frame_stack(frame)
    assert list(frame_stack) == [frame.f_back, frame]


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


def test_greenlet_timer():
    gevent = pytest.importorskip('gevent', '1')
    from profiling.timers.greenlet import GreenletTimer
    def light():
        factorial(10)
        gevent.sleep(0.1)
        factorial(10)
    def heavy():
        factorial(10000)
    # using default timer.
    normal_profiler = Profiler(top_frame=sys._getframe())
    with profiling(normal_profiler):
        gevent.spawn(light).join(0)
        gevent.spawn(heavy)
        gevent.wait()
    stat1 = find_stat(normal_profiler.stats, 'light')
    stat2 = find_stat(normal_profiler.stats, 'heavy')
    # light() ends later than heavy().  its total time includes heavy's also.
    assert stat1.total_time >= stat2.total_time
    # using greenlet timer.
    greenlet_profiler = Profiler(GreenletTimer(), top_frame=sys._getframe())
    with profiling(greenlet_profiler):
        gevent.spawn(light).join(0)
        gevent.spawn(heavy)
        gevent.wait()
    stat1 = find_stat(greenlet_profiler.stats, 'light')
    stat2 = find_stat(greenlet_profiler.stats, 'heavy')
    # light() ends later than heavy() like the above case.  but the total time
    # doesn't include heavy's.  each greenlets have isolated cpu time.
    assert stat1.total_time < stat2.total_time
