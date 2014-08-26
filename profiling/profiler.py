# -*- coding: utf-8 -*-
"""
    profiling.timers.greenlet
    ~~~~~~~~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
from collections import deque
import os
import sys

from .sortkeys import by_total_time
from .timers import Timer


__all__ = ['Profiler', 'Stat']


class Profiler(object):

    timer = None
    stat = None
    times = None
    started_at = None
    stopped_at = None

    def __init__(self, timer=None):
        super(Profiler, self).__init__()
        if timer is None:
            timer = Timer()
        self.timer = timer
        self.stat = Stat()
        self.times = {}

    def start(self):
        sys.setprofile(self._profile)
        self.timer.start()
        self.started_at = self.timer.clock()

    def stop(self):
        self.timer.stop()
        sys.setprofile(None)
        self.stat.record(self.timer.clock() - self.started_at)

    def _profile(self, frame, event, arg):
        time = self.timer()
        if event.startswith('c_'):
            return
        # find the parent stat
        parent_stat = self.stat
        for f in self._get_frame_stack(frame.f_back):
            try:
                parent_stat = parent_stat[f.f_code]
            except KeyError:
                parent_stat = self.stat
                break
        # record
        if event in ('call'):
            self._entered(frame, time, parent_stat)
        elif event in ('return', 'exception'):
            self._leaved(frame, time, parent_stat)

    def _entered(self, frame, time, parent_stat):
        self.times[frame] = time
        code = frame.f_code
        if code not in parent_stat:
            parent_stat.add_child(Stat(code))

    def _leaved(self, frame, time, parent_stat):
        try:
            stat = parent_stat[frame.f_code]
            timespan = time - self.times.pop(frame)
        except KeyError:
            return
        stat.record(timespan)

    def _get_frame_stack(self, frame):
        frame_stack = deque()
        while frame is not None:
            frame_stack.appendleft(frame)
            frame = frame.f_back
        return frame_stack

    def _repr_frame(self, frame):
        co = frame.f_code
        return \
            '{0}:{1} {2}'.format(co.co_filename, co.co_firstlineno, co.co_name)


class Stat(object):

    def __init__(self, code=None):
        super(Stat, self).__init__()
        self.code = code
        self.children = {}
        self.count = 0
        self.total_time = 0.

    def get_child(self, code, default=None):
        return self.children.get(code, default)

    def add_child(self, stat):
        self.children[stat.code] = stat

    def record(self, timespan):
        assert timespan >= 0
        self.count += 1
        self.total_time += timespan

    def __iter__(self):
        return self.children.itervalues()

    def __contains__(self, code):
        return code in self.children

    def __getitem__(self, code):
        return self.children[code]

    def sorted(self, order=by_total_time):
        return sorted(self, key=order, reverse=True)

    @property
    def name(self):
        co = self.code
        if co.co_filename.startswith('<'):
            return co.co_filename
        filename = os.path.basename(co.co_filename)
        name = '{0}:{1}'.format(filename, co.co_firstlineno)
        if co.co_name != '<module>':
            name = '{0} at {1}'.format(co.co_name, name)
        return name

    @property
    def own_time(self):
        sub_time = sum(stat.total_time for stat in self)
        return max(0., self.total_time - sub_time)

    @property
    def total_time_per_call(self):
        return self.total_time / self.count

    @property
    def own_time_per_call(self):
        return self.own_time / self.count

    def __repr__(self):
        class_name = type(self).__name__
        fmt = '<{0} {1}, count={2} total_time={3:.6f} own_time={4:.6f}>'
        return fmt.format(
            class_name, self.name, self.count, self.total_time, self.own_time)
