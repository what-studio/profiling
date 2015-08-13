# -*- coding: utf-8 -*-
"""
    profiling.profiler
    ~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import

from .stats import FrozenStatistics, RecordingStatistics
from .utils import Runnable
from .viewer import StatisticsTable


__all__ = ['Profiler', 'ProfilerWrapper']


class Profiler(Runnable):
    """The base class for profiler."""

    #: A widget class which extends :class:`profiling.viewer.StatisticsTable`.
    table_class = StatisticsTable

    #: The root recording statistics.
    stats = None

    top_frame = None
    top_code = None

    def __init__(self, top_frame=None, top_code=None):
        self.top_frame = top_frame
        self.top_code = top_code
        self.clear()

    def exclude_code(self, code):
        """Excludes statistics of the given code."""
        try:
            self.stats.remove_child(code)
        except KeyError:
            pass

    def result(self):
        """Gets the frozen statistics to serialize by Pickle."""
        return FrozenStatistics(self.stats)

    def clear(self):
        """Clears or initializes the recording statistics."""
        if self.stats is None:
            self.stats = RecordingStatistics()
        else:
            self.stats.clear()


class ProfilerWrapper(Profiler):

    for attr in ['table_class', 'stats', 'top_frame', 'top_code',
                 'result', 'clear', 'is_running']:
        f = lambda self, attr=attr: getattr(self.profiler, attr)
        locals()[attr] = property(f)
        del f

    def __init__(self, profiler):
        self.profiler = profiler
