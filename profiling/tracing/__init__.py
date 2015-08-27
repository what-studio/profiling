# -*- coding: utf-8 -*-
"""
    profiling.tracing
    ~~~~~~~~~~~~~~~~~

    Profiles deterministically by :func:`sys.setprofile`.

"""
from __future__ import absolute_import
import sys
import threading

from .. import sortkeys
from ..profiler import Profiler
from ..stats import RecordingStatistics, VoidRecordingStatistics
from ..utils import deferral, frame_stack
from ..viewer import StatisticsTable, fmt
from .timers import Timer


__all__ = ['TracingProfiler', 'TracingStatisticsTable']


TIMER_CLASS = Timer


class TracingStatisticsTable(StatisticsTable):

    columns = [
        ('FUNCTION', 'left', ('weight', 1), sortkeys.by_function),
        ('CALLS', 'right', (6,), sortkeys.by_own_hits),
        ('OWN', 'right', (6,), sortkeys.by_own_time),
        ('/CALL', 'right', (6,), sortkeys.by_own_time_per_call),
        ('%', 'left', (4,), None),
        ('DEEP', 'right', (6,), sortkeys.by_deep_time),
        ('/CALL', 'right', (6,), sortkeys.by_deep_time_per_call),
        ('%', 'left', (4,), None),
    ]
    order = sortkeys.by_deep_time

    def make_cells(self, node, stats):
        yield fmt.make_stat_text(stats)
        yield fmt.make_int_or_na_text(stats.own_hits)
        yield fmt.make_time_text(stats.own_time)
        yield fmt.make_time_text(stats.own_time_per_call)
        yield fmt.make_percent_text(stats.own_time, self.cpu_time)
        yield fmt.make_time_text(stats.deep_time)
        yield fmt.make_time_text(stats.deep_time_per_call)
        yield fmt.make_percent_text(stats.deep_time, self.cpu_time)


class TracingProfiler(Profiler):
    """The tracing profiler."""

    table_class = TracingStatisticsTable

    #: The CPU timer.  Usually it is an instance of :class:`profiling.tracing.
    #: timers.Timer`.
    timer = None

    def __init__(self, top_frame=None, top_code=None, timer=None):
        timer = timer or TIMER_CLASS()
        if not isinstance(timer, Timer):
            raise TypeError('Not a timer instance')
        super(TracingProfiler, self).__init__(top_frame, top_code)
        self.timer = timer
        self._times_entered = {}

    def _profile(self, frame, event, arg):
        """The callback function to register by :func:`sys.setprofile`."""
        # c = event.startswith('c_')
        if event.startswith('c_'):
            return
        frames = frame_stack(frame, self.top_frame, self.top_code)
        frames.pop()
        if not frames:
            return
        time = self.timer()
        void = VoidRecordingStatistics
        parent_stats = self.stats
        for f in frames:
            parent_stats = parent_stats.ensure_child(f.f_code, void)
        code = frame.f_code
        frame_key = id(frame)
        # if c:
        #     event = event[2:]
        #     code = mock_code(arg.__name__)
        #     frame_key = id(arg)
        # record
        if event == 'call':
            self.record_entering(time, code, frame_key, parent_stats)
        elif event == 'return':
            self.record_leaving(time, code, frame_key, parent_stats)

    def record_entering(self, time, code, frame_key, parent_stats):
        """Entered to a function call."""
        stats = parent_stats.ensure_child(code, RecordingStatistics)
        self._times_entered[(code, frame_key)] = time
        stats.own_hits += 1

    def record_leaving(self, time, code, frame_key, parent_stats):
        """Left from a function call."""
        try:
            stats = parent_stats.get_child(code)
            time_entered = self._times_entered.pop((code, frame_key))
        except KeyError:
            return
        time_elapsed = time - time_entered
        stats.deep_time += max(0, time_elapsed)

    def run(self):
        if sys.getprofile() is not None:
            # NOTE: There's no threading.getprofile().
            # The profiling function will be stored at threading._profile_hook
            # but it's not documented.
            raise RuntimeError('Another profiler already registered')
        with deferral() as defer:
            sys.setprofile(self._profile)
            defer(sys.setprofile, None)
            threading.setprofile(self._profile)
            defer(threading.setprofile, None)
            self.timer.start(self)
            defer(self.timer.stop)
            yield
            self._times_entered.clear()
