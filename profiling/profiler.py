# -*- coding: utf-8 -*-
"""
   profiling.profiler
   ~~~~~~~~~~~~~~~~~~

   :copyright: (c) 2014-2017, What! Studio
   :license: BSD, see LICENSE for more details.

"""
from __future__ import absolute_import

import time

from profiling.stats import RecordingStatistics
from profiling.utils import frame_stack, Runnable
from profiling.viewer import StatisticsTable, StatisticsViewer


__all__ = ['Profiler', 'ProfilerWrapper']


class Profiler(Runnable):
    """The base class for profiler."""

    #: A widget class which extends :class:`profiling.viewer.StatisticsTable`.
    table_class = StatisticsTable

    #: The root recording statistics.
    stats = None

    base_frame = None
    base_code = None
    ignored_frames = ()
    ignored_codes = ()

    def __init__(self, base_frame=None, base_code=None,
                 ignored_frames=(), ignored_codes=()):
        self.base_frame = base_frame
        self.base_code = base_code
        self.ignored_frames = ignored_frames
        self.ignored_codes = ignored_codes
        self.stats = RecordingStatistics()

    def start(self):
        self._cpu_time_started = time.clock()
        self._wall_time_started = time.time()
        self.stats.clear()
        return super(Profiler, self).start()

    def frame_stack(self, frame):
        return frame_stack(frame, self.base_frame, self.base_code,
                           self.ignored_frames, self.ignored_codes)

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

    def make_viewer(self, title=None, at=None):
        """Makes a statistics viewer from the profiling result.
        """
        viewer = StatisticsViewer()
        viewer.set_profiler_class(self.__class__)
        stats, cpu_time, wall_time = self.result()
        viewer.set_result(stats, cpu_time, wall_time, title=title, at=at)
        viewer.activate()
        return viewer

    def run_viewer(self, title=None, at=None, mono=False,
                   *loop_args, **loop_kwargs):
        """A shorter form of:

        ::

           viewer = profiler.make_viewer()
           loop = viewer.loop()
           loop.run()

        """
        viewer = self.make_viewer(title, at=at)
        loop = viewer.loop(*loop_args, **loop_kwargs)
        if mono:
            loop.screen.set_terminal_properties(1)
        loop.run()


class ProfilerWrapper(Profiler):

    for attr in ['table_class', 'stats', 'top_frame', 'top_code', 'result',
                 'is_running']:
        f = lambda self, attr=attr: getattr(self.profiler, attr)
        locals()[attr] = property(f)
        del f

    def __init__(self, profiler):
        self.profiler = profiler
