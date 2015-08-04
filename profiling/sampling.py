# -*- coding: utf-8 -*-
"""
    profiling.sampling
    ~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
import signal
import sys
import time

import six.moves._thread as _thread

from .profiler import Profiler
from .stats import RecordingStatistic, RecordingStatistics
from .utils import frame_stack


__all__ = ['SamplingProfiler']


class SamplingProfiler(Profiler):

    stats_class = RecordingStatistics

    interval = 0.01

    main_thread_id = _thread.get_ident()

    def __init__(self, top_frame=None, top_code=None, interval=None):
        super(SamplingProfiler, self).__init__(top_frame, top_code)
        if interval is not None:
            self.interval = interval

    def handle_signal(self, signum, frame):
        frames = sys._current_frames()
        # replace frame of the main thread with the interrupted frame.
        frames[self.main_thread_id] = frame
        for frame_ in frames.values():
            self.sample(frame_)

    def sample(self, frame):
        """Samples the given frame."""
        frames = frame_stack(frame, self.top_frame, self.top_code)
        frames.pop()
        if not frames:
            return
        # count function call.
        parent_stat = self.stats
        for f in frames:
            parent_stat = parent_stat.ensure_child(f.f_code)
        code = frame.f_code
        try:
            stat = parent_stat.get_child(code)
        except KeyError:
            stat = RecordingStatistic(code)
            parent_stat.add_child(code, stat)
        stat.record_call()

    def run(self):
        prev_handler = signal.signal(signal.SIGPROF, self.handle_signal)
        prev_itimer = signal.setitimer(signal.ITIMER_PROF,
                                       self.interval, self.interval)
        try:
            if prev_itimer != (0.0, 0.0):
                raise RuntimeError('Another SIGPROF interval timer exists')
            self.stats.record_starting(time.clock())
            yield
            self.stats.record_stopping(time.clock())
        finally:
            signal.setitimer(signal.ITIMER_PROF, *prev_itimer)
            signal.signal(signal.SIGPROF, prev_handler)
