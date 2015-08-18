# -*- coding: utf-8 -*-
"""
    profiling.profiler
    ~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
import time

from .stats import FrozenStatistic, RecordingStatistic
from .utils import Runnable
from .viewer import StatisticsTable


__all__ = ['Profiler', 'ProfilerWrapper']


class Profiler(Runnable):
    """The base class for profiler."""

    #: A widget class which extends :class:`profiling.viewer.StatisticsTable`.
    table_class = StatisticsTable

    #: The root recording statistics.
    stats = None

    stats_slots = ('own_count', 'deep_time')

    top_frame = None
    top_code = None

    def __init__(self, top_frame=None, top_code=None):
        self.top_frame = top_frame
        self.top_code = top_code
        self.clear()

    def start(self):
        self._cpu_time_started = time.clock()
        self._wall_time_started = time.time()
        return super(Profiler, self).start()

    def exclude_code(self, code):
        """Excludes statistics of the given code."""
        try:
            self.stats.remove_child(code)
        except KeyError:
            pass

    def result(self):
        """Gets the frozen statistics to serialize by Pickle."""
        try:
            cpu_time = max(0, time.clock() - self._cpu_time_started)
            wall_time = max(0, time.time() - self._wall_time_started)
        except AttributeError:
            cpu_time = wall_time = 0.0
        frozen_stats = FrozenStatistic(self.stats, self.stats_slots)
        return (frozen_stats, cpu_time, wall_time)

    def clear(self):
        """Clears or initializes the recording statistics."""
        if self.stats is None:
            self.stats = RecordingStatistic(None)
        else:
            self.stats.clear()
        try:
            del self._cpu_time_started
            del self._wall_time_started
        except AttributeError:
            pass


class ProfilerWrapper(Profiler):

    for attr in ['table_class', 'stats', 'top_frame', 'top_code',
                 'result', 'clear', 'is_running']:
        f = lambda self, attr=attr: getattr(self.profiler, attr)
        locals()[attr] = property(f)
        del f

    def __init__(self, profiler):
        self.profiler = profiler
