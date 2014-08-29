# -*- coding: utf-8 -*-
"""
    profiling.profiler
    ~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
from collections import deque
import inspect
import sys
import time

from .sortkeys import by_total_time
from .timers import Timer


__all__ = ['Profiler', 'Stat']


class Profiler(object):

    timer = None
    stats = None

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
        sys.setprofile(self._profile)
        self.timer.start()
        self.stats.record_starting(self.timer.clock())

    def stop(self):
        self.stats.record_stopping(self.timer.clock())
        self.timer.stop()
        sys.setprofile(None)

    def clear(self):
        try:
            self.stats.clear()
        except AttributeError:
            self.stats = Statistics()

    def _profile(self, frame, event, arg):
        """The callback function to register by :func:`sys.setprofile`."""
        time = self.timer()
        if event.startswith('c_'):
            # ignore c_call, c_return, c_exception
            return
        # find the parent stat
        parent_stat = self.stats
        for f in self._frame_stack(frame.f_back):
            code = f.f_code
            try:
                parent_stat = parent_stat.get_child(code)
            except KeyError:
                new_parent_stat = VoidStat(code)
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
        while frame is not None:
            frame_stack.appendleft(frame)
            frame = frame.f_back
        return frame_stack


class Stat(object):
    """Statistic."""

    name = None
    filename = None
    lineno = None
    module = None
    calls = 0
    total_time = 0.0

    def __init__(self, name=None, filename=None, lineno=None, module=None):
        super(Stat, self).__init__()
        if name is not None:
            self.name = name
        if filename is not None:
            self.filename = filename
        if lineno is not None:
            self.lineno = lineno
        if module is not None:
            self.module = module

    def __iter__(self):
        """Override it to walk child stats."""
        return iter(())

    def __len__(self):
        """Override it to calls child stats."""
        return 0

    @property
    def regular_name(self):
        name, module = self.name, self.module
        if name and module:
            return ':'.join([module, name])
        return name or module

    @property
    def own_time(self):
        sub_time = sum(stat.total_time for stat in self)
        return max(0., self.total_time - sub_time)

    @property
    def total_time_per_call(self):
        try:
            return self.total_time / self.calls
        except ZeroDivisionError:
            return 0.0

    @property
    def own_time_per_call(self):
        try:
            return self.own_time / self.calls
        except ZeroDivisionError:
            return 0.0

    def sorted(self, order=by_total_time):
        return sorted(self, key=order, reverse=True)

    def __repr__(self):
        class_name = type(self).__name__
        name_string = self.regular_name
        name_string = '' if name_string is None else name_string + ', '
        fmt = '<{0} {1}calls={2} total_time={3:.6f} own_time={4:.6f}>'
        return fmt.format(class_name, name_string, self.calls,
                          self.total_time, self.own_time)


class RecordingStat(Stat):
    """Recordig statistic measures execution time of a code."""

    def __init__(self, code=None):
        super(RecordingStat, self).__init__()
        self.code = code
        self.children = {}
        self._times_entered = {}

    @property
    def name(self):
        if self.code is None:
            return
        name = self.code.co_name
        if name == '<module>':
            return
        return name

    @property
    def filename(self):
        return self.code and self.code.co_filename

    @property
    def lineno(self):
        return self.code and self.code.co_firstlineno

    @property
    def module(self):
        if self.code is None:
            return
        module = inspect.getmodule(self.code)
        if not module:
            return
        return module.__name__

    def record_entering(self, time, frame=None):
        self._times_entered[id(frame)] = time
        self.calls += 1

    def record_leaving(self, time, frame=None):
        time_entered = self._times_entered.pop(id(frame))
        time_elapsed = time - time_entered
        self.total_time += max(0, time_elapsed)

    def clear(self):
        self.code = None
        self.children.clear()
        self.calls = Stat.calls
        self.total_time = Stat.total_time
        self._times_entered.clear()

    def get_child(self, code):
        return self.children[code]

    def add_child(self, code, stat):
        self.children[code] = stat

    def __iter__(self):
        return self.children.itervalues()

    def __len__(self):
        return len(self.children)

    def __getitem__(self, code):
        return self.get_child(code)

    def __contains__(self, code):
        return code in self.children


class Statistics(RecordingStat):
    """Thr root statistic of the statistics tree."""

    cpu_time = 0.0
    wall_time = 0.0

    name = None
    filename = None
    lineno = None
    module = None

    @property
    def cpu_usage(self):
        try:
            return self.cpu_time / self.wall_time
        except ZeroDivisionError:
            return 0.0

    @property
    def total_time(self):
        return self.wall_time

    @property
    def own_time(self):
        return self.cpu_time

    wall = time.time

    def record_starting(self, time):
        self._cpu_time_started = time
        self._wall_time_started = self.wall()

    def record_stopping(self, time):
        try:
            self.cpu_time = max(0, time - self._cpu_time_started)
            self.wall_time = max(0, self.wall() - self._wall_time_started)
        except AttributeError:
            raise RuntimeError('Starting does not recorded.')
        self.calls = 1
        del self._cpu_time_started
        del self._wall_time_started

    record_entering = NotImplemented
    record_leaving = NotImplemented

    def clear(self):
        self.children.clear()
        self.calls = Stat.calls
        self.cpu_time = Stat.cpu_time
        self.wall_time = Stat.wall_time
        try:
            del self._cpu_time_started
        except AttributeError:
            pass
        try:
            del self._wall_time_started
        except AttributeError:
            pass

    def __repr__(self):
        class_name = type(self).__name__
        return '<{0} cpu_usage={1:.2%}>'.format(class_name, self.cpu_usage)


class VoidStat(RecordingStat):
    """Statistic for an absent frame."""

    @property
    def total_time(self):
        return sum(stat.total_time for stat in self)

    def record_entering(self, time, frame=None):
        pass

    def record_leaving(self, time, frame=None):
        pass

    clear = NotImplemented


class FrozenStat(Stat):
    """Frozen :class:`Stat` to serialize by Pickle."""

    _state_slots = [
        'name', 'filename', 'lineno', 'module',
        'calls', 'total_time', 'children']

    def __init__(self, stat):
        args = (stat.name, stat.filename, stat.lineno, stat.module)
        super(FrozenStat, self).__init__(*args)
        self.calls = stat.calls
        self.total_time = stat.total_time
        self.children = map(type(self), stat)

    def __iter__(self):
        return iter(self.children)

    def __len__(self):
        return len(self.children)

    def __getstate__(self):
        return tuple(getattr(self, attr) for attr in self._state_slots)

    def __setstate__(self, state):
        for attr, val in zip(self._state_slots, state):
            setattr(self, attr, val)


class FrozenStatistics(FrozenStat, Statistics):
    """Frozen :class:`Statistics` to serialize by Pickle."""

    _state_slots = ['cpu_time', 'wall_time', 'children']

    def __init__(self, stats):
        Stat.__init__(self)
        self.cpu_time = stats.cpu_time
        self.wall_time = stats.wall_time
        self.children = map(FrozenStat, stats)
