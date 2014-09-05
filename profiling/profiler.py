# -*- coding: utf-8 -*-
"""
    profiling.profiler
    ~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
from collections import deque
import sys
import threading

from .stats import (
    RecordingStat, RecordingStatistics, VoidRecordingStat, FrozenStatistics)
from .timers import Timer


__all__ = ['Profiler']


class Profiler(object):

    timer = None
    stats = None
    frame = None

    def __init__(self, timer=None):
        super(Profiler, self).__init__()
        if timer is None:
            timer = Timer()
        self.timer = timer
        self.clear()

    def frozen_stats(self):
        """Gets the frozen statistics to serialize by Pickle."""
        return FrozenStatistics(self.stats)

    def start(self):
        if sys.getprofile() is not None:
            raise RuntimeError('Another profiler already registered.')
        self.frame = sys._getframe().f_back
        sys.setprofile(self._profile)
        threading.setprofile(self._profile)
        self.timer.start()
        self.stats.record_starting(self.timer.clock())

    def stop(self):
        self.stats.record_stopping(self.timer.clock())
        self.timer.stop()
        threading.setprofile(None)
        sys.setprofile(None)
        self.frame = None

    def clear(self):
        try:
            self.stats.clear()
        except AttributeError:
            self.stats = RecordingStatistics()

    def _profile(self, frame, event, arg):
        """The callback function to register by :func:`sys.setprofile`."""
        time = self.timer()
        if event.startswith('c_'):
            # c_call, c_return, c_exception
            event = event[2:]
        # find the parent stat
        parent_stat = self.stats
        for f in self._frame_stack(frame.f_back):
            code = f.f_code
            try:
                parent_stat = parent_stat.get_child(code)
            except KeyError:
                new_parent_stat = VoidRecordingStat(code)
                parent_stat.add_child(code, new_parent_stat)
                parent_stat = new_parent_stat
        # record
        if event == 'call':
            time = self.timer()
            self._entered(time, frame, parent_stat)
        elif event in ('return', 'exception'):
            self._leaved(time, frame, parent_stat)

    def _entered(self, time, frame, parent_stat):
        code = frame.f_code
        try:
            stat = parent_stat.get_child(code)
        except KeyError:
            stat = RecordingStat(code)
            parent_stat.add_child(code, stat)
        stat.record_entering(time, frame)

    def _leaved(self, time, frame, parent_stat):
        try:
            stat = parent_stat[frame.f_code]
            stat.record_leaving(time, frame)
        except KeyError:
            pass
        # stat.record(time)

    def _frame_stack(self, frame):
        frame_stack = deque()
        while frame is not None and frame is not self.frame:
            frame_stack.appendleft(frame)
            frame = frame.f_back
        return frame_stack
