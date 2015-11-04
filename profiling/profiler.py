# -*- coding: utf-8 -*-
"""
   profiling.profiler
   ~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import

import time

from .stats import RecordingStatistics
from .utils import frame_stack, Runnable
from .viewer import StatisticsTable, StatisticsViewer


__all__ = ['Profiler', 'ProfilerWrapper']


class Profiler(Runnable):
    """The base class for profiler."""

    #: A widget class which extends :class:`profiling.viewer.StatisticsTable`.
    table_class = StatisticsTable

    #: The root recording statistics.
    stats = None

    top_frames = ()
    top_codes = ()
    upper_frames = ()
    upper_codes = ()

    def __init__(self, top_frames=(), top_codes=(),
                 upper_frames=(), upper_codes=()):
        self.top_frames = top_frames
        self.top_codes = top_codes
        self.upper_frames = upper_frames
        self.upper_codes = upper_codes
        self.stats = RecordingStatistics()

    def start(self):
        self._cpu_time_started = time.clock()
        self._wall_time_started = time.time()
        self.stats.clear()
        return super(Profiler, self).start()

    def frame_stack(self, frame):
        return frame_stack(frame, self.top_frames, self.top_codes,
                           self.upper_frames, self.upper_codes)

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
        return (self.stats, cpu_time, wall_time)

    def make_viewer(self, title=None, at=None, mono=False,
                    *loop_args, **loop_kwargs):
        """Makes a statistics viewer and that's loop from the profiling result.
        """
        viewer = StatisticsViewer()
        viewer.set_profiler_class(self.__class__)
        stats, cpu_time, wall_time = self.result()
        viewer.set_result(stats, cpu_time, wall_time, title=title, at=at)
        viewer.activate()
        loop = viewer.loop(*loop_args, **loop_kwargs)
        if mono:
            loop.screen.set_terminal_properties(1)
        return (viewer, loop)

    def run_viewer(self, *args, **kwargs):
        """A shorter form of:

        ::

           viewer, loop = profiler.make_viewer()
           loop.run()

        """
        viewer, loop = self.make_viewer(*args, **kwargs)
        loop.run()


class ProfilerWrapper(Profiler):

    for attr in ['table_class', 'stats', 'top_frame', 'top_code', 'result',
                 'is_running']:
        f = lambda self, attr=attr: getattr(self.profiler, attr)
        locals()[attr] = property(f)
        del f

    def __init__(self, profiler):
        self.profiler = profiler
