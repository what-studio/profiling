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
        self.stat = RecordingStat()
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
            # ignore c_call, c_return, c_exception
            return
        # find the parent stat
        parent_stat = self.stat
        for f in self._frame_stack(frame.f_back):
            try:
                parent_stat = parent_stat.get_child(f.f_code)
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
            parent_stat.add_child(code, RecordingStat(code))

    def _leaved(self, frame, time, parent_stat):
        try:
            stat = parent_stat[frame.f_code]
            timespan = time - self.times.pop(frame)
        except KeyError:
            return
        stat.record(timespan)

    def _frame_stack(self, frame):
        frame_stack = deque()
        while frame is not None:
            frame_stack.appendleft(frame)
            frame = frame.f_back
        return frame_stack


class Stat(object):
    """Statistic."""

    name = None
    filename = None
    lineno = None
    count = 0
    total_time = 0.0

    def __init__(self, name=None, filename=None, lineno=None):
        super(Stat, self).__init__()
        self.name = name
        self.filename = filename
        self.lineno = lineno

    def __iter__(self):
        """Override it to walk child stats."""
        return iter(())

    @property
    def regular_name(self):
        if self.name is None:
            return
        elif self.filename.startswith('<'):
            # e.g. <string>
            return self.filename
        filename = os.path.basename(self.filename)
        regular_name = '{0}:{1}'.format(filename, self.lineno)
        if self.name == '<module>':
            # e.g. mycode.py:89
            pass
        else:
            # e.g. myfunc at mycode.py:123
            regular_name = '{0} at {1}'.format(self.name, regular_name)
        return regular_name

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

    def sorted(self, order=by_total_time):
        return sorted(self, key=order, reverse=True)

    def frozen(self):
        """Gets this stat as frozen."""
        return FrozenStat(self)

    def __repr__(self):
        class_name = type(self).__name__
        name_string = self.regular_name
        name_string = '' if name_string is None else name_string + ', '
        fmt = '<{0} {1}count={2} total_time={3:.6f} own_time={4:.6f}>'
        return fmt.format(class_name, name_string, self.count,
                          self.total_time, self.own_time)


class RecordingStat(Stat):
    """Recordig statistic measures execution time of a code."""

    def __init__(self, code=None):
        if code is None:
            args = ()
        else:
            args = (code.co_name, code.co_filename, code.co_firstlineno)
        super(RecordingStat, self).__init__(*args)
        self.children = {}

    def record(self, timespan):
        assert timespan >= 0
        self.count += 1
        self.total_time += timespan

    def get_child(self, code):
        return self.children[code]

    def add_child(self, code, stat):
        self.children[code] = stat

    def __iter__(self):
        return self.children.itervalues()

    def __getitem__(self, code):
        return self.get_child(code)

    def __contains__(self, code):
        return code in self.children


class FrozenStat(Stat):
    """Picklable statistic."""

    def __init__(self, stat):
        super(FrozenStat, self).__init__(stat.name, stat.filename, stat.lineno)
        self.count = stat.count
        self.total_time = stat.total_time
        self.children = map(type(self), stat)

    def __iter__(self):
        return iter(self.children)

    def frozen(self):
        """Already frozen."""
        return self
