# -*- coding: utf-8 -*-
import sys
import time

import pytest

from profiling.__main__ import spawn_thread
from profiling.profiler import Profiler
from profiling.timers.greenlet import GreenletTimer
from profiling.timers.thread import ThreadTimer, YappiTimer
from utils import factorial, find_stat, profiling


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
    _test_contextual_timer(ThreadTimer(), time.sleep, spawn_thread)


def test_yappi_timer():
    pytest.importorskip('yappi')
    _test_contextual_timer(YappiTimer(), time.sleep, spawn_thread)


def test_greenlet_timer():
    gevent = pytest.importorskip('gevent', '1')
    _test_contextual_timer(GreenletTimer(), gevent.sleep, gevent.spawn)


@pytest.mark.skipif(sys.version_info >= (3, 3),
                    reason='ThreadTimer works well on Python 3.3 or later.')
def test_thread_timer_runtime_error():
    with pytest.raises(RuntimeError):
        ThreadTimer()
