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


__all__ = ['Sampler', 'ItimerSampler', 'ThreadSampler']


DEFAULT_INTERVAL = 1e-3  # 1ms


class Sampler(Runnable):
    """The base class for samplers."""

    #: Sampling interval.
    interval = DEFAULT_INTERVAL

    def __init__(self, interval=DEFAULT_INTERVAL):
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


class ThreadSampler(Sampler):

    def sample_periodically(self, profiler):
        sampling_thread_id = _thread.get_ident()
        while profiler.is_running():
            time.sleep(self.interval)
            frames = self.current_frames()
            # remove here the sampling thread.
            del frames[sampling_thread_id]
            for frame in frames.values():
                profiler.sample(frame)

    def run(self, profiler):
        t = threading.Thread(target=self.sample_periodically, args=(profiler,))
        t.start()
        yield
        t.join()
