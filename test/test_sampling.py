# -*- coding: utf-8 -*-
from __future__ import division

import os
import signal
import sys

import pytest

from _utils import find_stats, spin
from profiling.sampling import SamplingProfiler
from profiling.sampling.samplers import ItimerSampler, TracingSampler


def spin_100ms():
    spin(0.1)


def spin_500ms():
    spin(0.5)


def _test_sampling_profiler(sampler):
    profiler = SamplingProfiler(base_frame=sys._getframe(), sampler=sampler)
    with profiler:
        spin_100ms()
        spin_500ms()
    stat1 = find_stats(profiler.stats, 'spin_100ms')
    stat2 = find_stats(profiler.stats, 'spin_500ms')
    ratio = stat1.deep_hits / stat2.deep_hits
    # 1:5 expaected, but tolerate (0.8~1.2):5
    assert 0.8 <= ratio * 5 <= 1.2


@pytest.mark.flaky(reruns=10)
def test_itimer_sampler():
    assert signal.getsignal(signal.SIGPROF) == signal.SIG_DFL
    try:
        _test_sampling_profiler(ItimerSampler(0.0001))
        # no crash caused by SIGPROF.
        assert signal.getsignal(signal.SIGPROF) == signal.SIG_IGN
        for x in range(10):
            os.kill(os.getpid(), signal.SIGPROF)
        # respect custom handler.
        handler = lambda *x: x
        signal.signal(signal.SIGPROF, handler)
        _test_sampling_profiler(ItimerSampler(0.0001))
        assert signal.getsignal(signal.SIGPROF) == handler
    finally:
        signal.signal(signal.SIGPROF, signal.SIG_DFL)


@pytest.mark.flaky(reruns=10)
def test_tracing_sampler():
    pytest.importorskip('yappi')
    _test_sampling_profiler(TracingSampler(0.0001))


@pytest.mark.flaky(reruns=10)
def test_tracing_sampler_does_not_sample_too_often():
    pytest.importorskip('yappi')
    # pytest-cov cannot detect a callback function registered by
    # :func:`sys.setprofile`.
    class fake_profiler(object):
        samples = []
        @classmethod
        def sample(cls, frame):
            cls.samples.append(frame)
        @classmethod
        def count_and_clear_samples(cls):
            count = len(cls.samples)
            del cls.samples[:]
            return count
    sampler = TracingSampler(0.1)
    sampler._profile(fake_profiler, None, None, None)
    assert fake_profiler.count_and_clear_samples() == 1
    sampler._profile(fake_profiler, None, None, None)
    assert fake_profiler.count_and_clear_samples() == 0
    spin(0.5)
    sampler._profile(fake_profiler, None, None, None)
    assert fake_profiler.count_and_clear_samples() == 1


def test_not_sampler():
    with pytest.raises(TypeError):
        SamplingProfiler(sampler=123)


def test_sample_1_depth():
    frame = sys._getframe()
    while frame.f_back is not None:
        frame = frame.f_back
    assert frame.f_back is None
    profiler = SamplingProfiler()
    profiler.sample(frame)
