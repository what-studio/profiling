# -*- coding: utf-8 -*-
"""
    profiling.profiler
    ~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
from collections import deque
import sys
import threading
import time

try:
    from . import speedup
except ImportError:
    speedup = False
from .stats import RecordingStat, RecordingStatistics, FrozenStatistics
from .timers import Timer


__all__ = ['Profiler']


class Profiler(object):
    """The profiler."""

    #: The CPU timer.  Usually it is an instance of :class:`profiling.timers.
    #: Timer`.
    timer = None

    #: The root recording statistics which is an instance of :class:`profiling.
    #: stats.RecordingStatistics`.
    stats = None

    top_frame = None
    top_code = None

    _running = False

    def __init__(self, timer=None, top_frame=None, top_code=None):
        if timer is None:
            timer = Timer()
        self.timer = timer
        self.top_frame = top_frame
        self.top_code = top_code
        self.clear()

    def result(self):
        """Gets the frozen statistics to serialize by Pickle."""
        return FrozenStatistics(self.stats)

    def start(self):
        if sys.getprofile() is not None:
            raise RuntimeError('Another profiler already registered.')
        self._running = True
        sys.setprofile(self._profile)
        threading.setprofile(self._profile)
        self.timer.start()
        self.stats.record_starting(time.clock())

    def stop(self):
        self.stats.record_stopping(time.clock())
        self.timer.stop()
        threading.setprofile(None)
        sys.setprofile(None)
        self._running = False

    def is_running(self):
        """Whether the profiler is running."""
        return self._running

    def clear(self):
        """Clears or initializes the recording statistics."""
        try:
            self.stats.clear()
        except AttributeError:
            self.stats = RecordingStatistics()

    if speedup:
        def _frame_stack(self, frame):
            """Returns a deque of frame stack."""
            return speedup.frame_stack(frame, self.top_frame, self.top_code)
    else:
        def _frame_stack(self, frame):
            """Returns a deque of frame stack."""
            frame_stack = deque()
            top_frame = self.top_frame
            top_code = self.top_code
            while frame is not None:
                frame_stack.appendleft(frame)
                if frame is top_frame or frame.f_code is top_code:
                    break
                frame = frame.f_back
            return frame_stack

    def _profile(self, frame, event, arg):
        """The callback function to register by :func:`sys.setprofile`."""
        time = self.timer()
        if event.startswith('c_'):
            return
        frame_stack = self._frame_stack(frame)
        frame_stack.pop()
        if not frame_stack:
            return
        parent_stat = self.stats
        for f in frame_stack:
            parent_stat = parent_stat.ensure_child(f.f_code)
        code = frame.f_code
        frame_key = id(frame)
        # if c:
        #     event = event[2:]
        #     code = mock_code(arg.__name__)
        #     frame_key = id(arg)
        # record
        if event in ('call',):
            time = self.timer()
            self._entered(time, code, frame_key, parent_stat)
        elif event in ('return', 'exception'):
            self._left(time, code, frame_key, parent_stat)

    def _entered(self, time, code, frame_key, parent_stat):
        """Entered to a function call."""
        try:
            stat = parent_stat.get_child(code)
        except KeyError:
            stat = RecordingStat(code)
            parent_stat.add_child(code, stat)
        stat.record_entering(time, frame_key)

    def _left(self, time, code, frame_key, parent_stat):
        """Left from a function call."""
        try:
            stat = parent_stat.get_child(code)
            stat.record_leaving(time, frame_key)
        except KeyError:
            pass
