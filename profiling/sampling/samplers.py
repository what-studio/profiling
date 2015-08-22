# -*- coding: utf-8 -*-
"""
    profiling.sampling.samplers
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
import functools
import signal
import sys
import threading
import time
import weakref

import six.moves._thread as _thread

from ..utils import Runnable


__all__ = ['Sampler', 'ItimerSampler', 'TracingSampler']


INTERVAL = 1e-3  # 1ms


class Sampler(Runnable):
    """The base class for samplers."""

    #: Sampling interval.
    interval = INTERVAL

    def __init__(self, interval=INTERVAL):
        self.interval = interval

    @staticmethod
    def current_frames():
        return sys._current_frames()


class ItimerSampler(Sampler):

    # keep the Id of the math thread.
    main_thread_id = _thread.get_ident()

    def handle_signal(self, profiler, signum, frame):
        frames = self.current_frames()
        # replace frame of the main thread with the interrupted frame.
        frames[self.main_thread_id] = frame
        for frame_ in frames.values():
            profiler.sample(frame_)

    def run(self, profiler):
        interval = self.interval
        handle = functools.partial(self.handle_signal, weakref.proxy(profiler))
        prev_handler = signal.signal(signal.SIGPROF, handle)
        prev_itimer = signal.setitimer(signal.ITIMER_PROF, interval, interval)
        yield
        signal.setitimer(signal.ITIMER_PROF, *prev_itimer)
        signal.signal(signal.SIGPROF, prev_handler)


class TracingSampler(Sampler):

    sampled_at = 0

    def _profile(self, profiler, frame, event, arg):
        t = time.clock()
        if t - self.sampled_at < self.interval:
            return
        self.sampled_at = t
        frames = self.current_frames()
        frames[_thread.get_ident()] = frame
        for frame in frames.values():
            profiler.sample(frame)

    def run(self, profiler):
        profile = functools.partial(self._profile, profiler)
        sys.setprofile(profile)
        threading.setprofile(profile)
        yield
        threading.setprofile(None)
        sys.setprofile(None)
