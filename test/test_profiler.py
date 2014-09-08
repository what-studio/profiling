# -*- coding: utf-8 -*-
from contextlib import contextmanager
import sys
import time

import pytest

from profiling.profiler import Profiler
from profiling.mocking import mock_code, mock_stacked_frame
from profiling.stats import FrozenStatistics, RecordingStatistics
from profiling.__main__ import spawn_thread


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


def _test_contextual_timer(timer, sleep, spawn):
    def light():
        factorial(10)
        sleep(0.1)
        factorial(10)
    def heavy():
        factorial(10000)
    def profile(profiler):
        with profiling(profiler):
            c1 = spawn(light)
            c1.join(0)
            c2 = spawn(heavy)
            for c in [c1, c2]:
                c.join()
        stat1 = find_stat(profiler.stats, 'light')
        stat2 = find_stat(profiler.stats, 'heavy')
        return (stat1, stat2)
    # using the default timer.
    # light() ends later than heavy().  its total time includes heavy's also.
    normal_profiler = Profiler(top_frame=sys._getframe())
    stat1, stat2 = profile(normal_profiler)
    assert stat1.total_time >= stat2.total_time
    # using the given timer.
    # light() ends later than heavy() like the above case.  but the total time
    # doesn't include heavy's.  each contexts should have isolated cpu time.
    contextual_profiler = Profiler(timer, top_frame=sys._getframe())
    stat1, stat2 = profile(contextual_profiler)
    assert stat1.total_time < stat2.total_time


@pytest.mark.skipif(sys.version_info < (3, 3),
                    reason='ThreadTimer requires Python 3.3 or later.')
def test_thread_timer():
    from profiling.timers.thread import ThreadTimer
    _test_contextual_timer(ThreadTimer(), time.sleep, spawn_thread)


def test_yappi_timer():
    pytest.importorskip('yappi')
    from profiling.timers.thread import YappiTimer
    _test_contextual_timer(YappiTimer(), time.sleep, spawn_thread)


def test_greenlet_timer():
    gevent = pytest.importorskip('gevent', '1')
    from profiling.timers.greenlet import GreenletTimer
    _test_contextual_timer(GreenletTimer(), gevent.sleep, gevent.spawn)
