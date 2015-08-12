# -*- coding: utf-8 -*-
"""
    profiling.sampling
    ~~~~~~~~~~~~~~~~~~

    Profiles statistically by ``signal.ITIMER_PROF``.

"""
from __future__ import absolute_import
import signal
import sys
import time

import six.moves._thread as _thread

from . import sortkeys
from .profiler import Profiler
from .stats import RecordingStatistic, VoidRecordingStatistic
from .utils import frame_stack
from .viewer import StatisticsTable, fmt


__all__ = ['SamplingProfiler', 'SamplingStatisticsTable']


class SamplingStatisticsTable(StatisticsTable):

    columns = [
        ('FUNCTION', 'left', ('weight', 1), sortkeys.by_function),
        ('SELF', 'right', (6,), sortkeys.by_self_count),
        ('%', 'left', (4,), None),
        ('DEEP', 'right', (6,), sortkeys.by_deep_count),
        ('%', 'left', (4,), None),
    ]
    order = sortkeys.by_deep_count

    def make_cells(self, node, stat, stats):
        yield fmt.make_stat_text(stat)
        yield fmt.make_int_or_na_text(stat.self_count)
        yield fmt.make_percent_text(stat.self_count, stats.deep_count)
        yield fmt.make_int_or_na_text(stat.deep_count)
        yield fmt.make_percent_text(stat.deep_count, stats.deep_count)


class SamplingProfiler(Profiler):

    table_class = SamplingStatisticsTable

    #: Sampling interval.  (1ms)
    interval = 1e-3

    # keep the Id of the math thread.
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
            parent_stat = \
                parent_stat.ensure_child(f.f_code, VoidRecordingStatistic)
        code = frame.f_code
        stat = parent_stat.ensure_child(code, RecordingStatistic)
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
