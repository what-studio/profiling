# -*- coding: utf-8 -*-
"""
   profiling.sampling.samplers
   ~~~~~~~~~~~~~~~~~~~~~~~~~~~

   :copyright: (c) 2014-2017, What! Studio
   :license: BSD, see LICENSE for more details.

"""
from __future__ import absolute_import

import functools
import signal
import sys
import threading
import weakref

import six.moves._thread as _thread

from profiling.utils import deferral, Runnable, thread_clock


__all__ = ['Sampler', 'ItimerSampler', 'TracingSampler']


INTERVAL = 1e-3  # 1ms


class Sampler(Runnable):
    """The base class for samplers."""

    #: Sampling interval.
    interval = INTERVAL

    def __init__(self, interval=INTERVAL):
        self.interval = interval


class ItimerSampler(Sampler):
    """Uses ``signal.ITIMER_PROF`` to sample running frames.

    .. note::

       ``signal.SIGPROF`` is triggeres by only the main thread.  If you need
       sample multiple threads, use :class:`TracingSampler` instead.

    """

    def handle_signal(self, profiler, signum, frame):
        profiler.sample(frame)

    def run(self, profiler):
        weak_profiler = weakref.proxy(profiler)
        handle = functools.partial(self.handle_signal, weak_profiler)
        t = self.interval
        with deferral() as defer:
            prev_handle = signal.signal(signal.SIGPROF, handle)
            if prev_handle == signal.SIG_DFL:
                # sometimes the process receives SIGPROF although the sampler
                # unsets the itimer.  If the previous handler was SIG_DFL, the
                # process will crash when received SIGPROF.  To prevent this
                # risk, it makes the process to ignore SIGPROF when it isn't
                # running if the previous handler was SIG_DFL.
                prev_handle = signal.SIG_IGN
            defer(signal.signal, signal.SIGPROF, prev_handle)
            prev_itimer = signal.setitimer(signal.ITIMER_PROF, t, t)
            defer(signal.setitimer, signal.ITIMER_PROF, *prev_itimer)
            yield


class TracingSampler(Sampler):
    """Uses :func:`sys.setprofile` and :func:`threading.setprofile` to sample
    running frames per thread.  It can be used at systems which do not support
    profiling signals.

    Just like :class:`profiling.tracing.timers.ThreadTimer`, `Yappi`_ is
    required for earlier than Python 3.3.

    .. _Yappi: https://code.google.com/p/yappi/

    """

    def __init__(self, *args, **kwargs):
        super(TracingSampler, self).__init__(*args, **kwargs)
        self.sampled_times = {}
        self.counter = 0

    def _profile(self, profiler, frame, event, arg):
        t = thread_clock()
        thread_id = _thread.get_ident()
        sampled_at = self.sampled_times.get(thread_id, 0)
        if t - sampled_at < self.interval:
            return
        self.sampled_times[thread_id] = t
        profiler.sample(frame)
        self.counter += 1
        if self.counter % 10000 == 0:
            self._clear_for_dead_threads()

    def _clear_for_dead_threads(self):
        for thread_id in sys._current_frames().keys():
            self.sampled_times.pop(thread_id, None)

    def run(self, profiler):
        profile = functools.partial(self._profile, profiler)
        with deferral() as defer:
            sys.setprofile(profile)
            defer(sys.setprofile, None)
            threading.setprofile(profile)
            defer(threading.setprofile, None)
            yield
