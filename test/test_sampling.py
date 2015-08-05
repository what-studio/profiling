# -*- coding: utf-8 -*-
from __future__ import division
import sys

import pytest

from profiling.sampling import SamplingProfiler
from utils import find_stat, profiling, spin


def spin_100ms():
    spin(0.1)


def spin_500ms():
    spin(0.5)


@pytest.mark.flaky(reruns=5)
def test_profiler():
    profiler = SamplingProfiler(top_frame=sys._getframe(), interval=0.0001)
    with profiling(profiler):
        spin_100ms()
        spin_500ms()
    stat1 = find_stat(profiler.stats, 'spin_100ms')
    stat2 = find_stat(profiler.stats, 'spin_500ms')
    ratio = stat1.all_calls / stat2.all_calls
    assert 0.8 <= ratio * 5 <= 1.2  # 1:5 expaected, but tolerate (0.8~1.2):5
