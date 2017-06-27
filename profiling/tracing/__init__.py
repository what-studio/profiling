# -*- coding: utf-8 -*-
"""
   profiling.tracing
   ~~~~~~~~~~~~~~~~~

   Profiles deterministically by :func:`sys.setprofile`.

   :copyright: (c) 2014-2017, What! Studio
   :license: BSD, see LICENSE for more details.

"""
from __future__ import absolute_import

import sys
import threading

from profiling import sortkeys
from profiling.profiler import Profiler
from profiling.stats import (
    RecordingStatistics, VoidRecordingStatistics as void)
from profiling.tracing.timers import Timer
from profiling.utils import deferral
from profiling.viewer import fmt, StatisticsTable


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

    #: The CPU time of profiling overhead.  It's the time spent in
    #: :meth:`_profile`.
    overhead = 0.0

    def __init__(self, base_frame=None, base_code=None,
                 ignored_frames=(), ignored_codes=(), timer=None):
        timer = timer or TIMER_CLASS()
        if not isinstance(timer, Timer):
            raise TypeError('Not a timer instance')
        base = super(TracingProfiler, self)
        base.__init__(base_frame, base_code, ignored_frames, ignored_codes)
        self.timer = timer
        self._times_entered = {}

    def _profile(self, frame, event, arg):
        """The callback function to register by :func:`sys.setprofile`."""
        # c = event.startswith('c_')
        if event.startswith('c_'):
            return
        time1 = self.timer()
        frames = self.frame_stack(frame)
        if frames:
            frames.pop()
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
        time2 = self.timer()
        self.overhead += time2 - time1
        if event == 'call':
            time = time2 - self.overhead
            self.record_entering(time, code, frame_key, parent_stats)
        elif event == 'return':
            time = time1 - self.overhead
            self.record_leaving(time, code, frame_key, parent_stats)
        time3 = self.timer()
        self.overhead += time3 - time2

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

    def result(self):
        base = super(TracingProfiler, self)
        frozen_stats, cpu_time, wall_time = base.result()
        return (frozen_stats, cpu_time - self.overhead, wall_time)

    def run(self):
        if sys.getprofile() is not None:
            # NOTE: There's no threading.getprofile().
            # The profiling function will be stored at threading._profile_hook
            # but it's not documented.
            raise RuntimeError('Another profiler already registered')
        with deferral() as defer:
            self._times_entered.clear()
            self.overhead = 0.0
            sys.setprofile(self._profile)
            defer(sys.setprofile, None)
            threading.setprofile(self._profile)
            defer(threading.setprofile, None)
            self.timer.start(self)
            defer(self.timer.stop)
            yield
