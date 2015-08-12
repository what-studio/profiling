# -*- coding: utf-8 -*-
"""
    profiling.tracing
    ~~~~~~~~~~~~~~~~~

    Profiles deterministically by :func:`sys.setprofile`.

"""
from __future__ import absolute_import
import sys
import threading
import time

from . import sortkeys
from .profiler import Profiler
from .stats import RecordingStatistic, VoidRecordingStatistic
from .timers import Timer
from .utils import frame_stack
from .viewer import StatisticsTable, fmt


__all__ = ['TracingProfiler', 'TracingStatisticsTable']


class TracingStatisticsTable(StatisticsTable):

    columns = [
        ('FUNCTION', 'left', ('weight', 1), sortkeys.by_function),
        ('CALLS', 'right', (6,), sortkeys.by_deep_count),
        ('SELF', 'right', (6,), sortkeys.by_self_time),
        ('/CALL', 'right', (6,), sortkeys.by_self_time_per_call),
        ('%', 'left', (4,), None),
        ('DEEP', 'right', (6,), sortkeys.by_deep_time),
        ('/CALL', 'right', (6,), sortkeys.by_deep_time_per_call),
        ('%', 'left', (4,), None),
    ]
    order = sortkeys.by_deep_time

    def make_cells(self, node, stat, stats):
        yield fmt.make_stat_text(stat)
        yield fmt.make_int_or_na_text(stat.deep_count)
        yield fmt.make_time_text(stat.self_time)
        yield fmt.make_time_text(stat.self_time_per_call)
        yield fmt.make_percent_text(stat.self_time, stats.cpu_time)
        yield fmt.make_time_text(stat.deep_time)
        yield fmt.make_time_text(stat.deep_time_per_call)
        yield fmt.make_percent_text(stat.deep_time, stats.cpu_time)


class TracingProfiler(Profiler):
    """The tracing profiler."""

    table_class = TracingStatisticsTable

    #: The CPU timer.  Usually it is an instance of :class:`profiling.timers.
    #: Timer`.
    timer = None

    def __init__(self, top_frame=None, top_code=None, timer=None):
        super(TracingProfiler, self).__init__(top_frame, top_code)
        if timer is None:
            timer = Timer()
        self.timer = timer

    def run(self):
        if sys.getprofile() is not None:
            raise RuntimeError('Another profiler already registered')
        sys.setprofile(self._profile)
        threading.setprofile(self._profile)
        self.timer.start()
        self.stats.record_starting(time.clock())
        yield
        self.stats.record_stopping(time.clock())
        self.timer.stop()
        threading.setprofile(None)
        sys.setprofile(None)

    def _profile(self, frame, event, arg):
        """The callback function to register by :func:`sys.setprofile`."""
        time = self.timer()
        # c = event.startswith('c_')
        if event.startswith('c_'):
            return
        frames = frame_stack(frame, self.top_frame, self.top_code)
        frames.pop()
        if not frames:
            return
        parent_stat = self.stats
        for f in frames:
            parent_stat = \
                parent_stat.ensure_child(f.f_code, VoidRecordingStatistic)
        code = frame.f_code
        frame_key = id(frame)
        # if c:
        #     event = event[2:]
        #     code = mock_code(arg.__name__)
        #     frame_key = id(arg)
        # record
        if event == 'call':
            time = self.timer()
            self._entered(time, code, frame_key, parent_stat)
        elif event == 'return':
            self._left(time, code, frame_key, parent_stat)

    def _entered(self, time, code, frame_key, parent_stat):
        """Entered to a function call."""
        stat = parent_stat.ensure_child(code, RecordingStatistic)
        stat.record_entering(time, frame_key)

    def _left(self, time, code, frame_key, parent_stat):
        """Left from a function call."""
        try:
            stat = parent_stat.get_child(code)
            stat.record_leaving(time, frame_key)
        except KeyError:
            pass
