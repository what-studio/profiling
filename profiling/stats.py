# -*- coding: utf-8 -*-
"""
    profiling.stats
    ~~~~~~~~~~~~~~~

    Statistic classes.

"""
from __future__ import absolute_import, division
from collections import defaultdict
import inspect
from threading import RLock
import time

from six import itervalues

from .sortkeys import by_deep_time


__all__ = ['Statistic', 'Statistics', 'RecordingStatistic',
           'RecordingStatistics', 'VoidRecordingStatistic', 'FrozenStatistic',
           'FrozenStatistics', 'FlatStatistic', 'FlatStatistics']


def failure(funcname, message='{class} not allow {func}.', exctype=TypeError):
    """Generates a method which raises an exception."""
    def func(self, *args, **kwargs):
        fmtopts = {'func': funcname, 'obj': self, 'class': type(self).__name__}
        raise exctype(message.format(**fmtopts))
    func.__name__ = funcname
    return func


# Statistic
# CountedStatistic
# TimedStatistic


class Statistic(object):
    """A statistic."""

    _state_slots = ['name', 'filename', 'lineno', 'module',
                    'own_count', 'deep_time']

    name = None
    filename = None
    lineno = None
    module = None
    own_count = 0
    deep_time = 0.0

    def __init__(self, stat=None, name=None, filename=None, lineno=None,
                 module=None):
        if stat is not None:
            assert name is filename is lineno is module is None
            name = stat.name
            filename = stat.filename
            lineno = stat.lineno
            module = stat.module
        if name is not None:
            self.name = name
        if filename is not None:
            self.filename = filename
        if lineno is not None:
            self.lineno = lineno
        if module is not None:
            self.module = module

    def __hash__(self):
        return hash((self.name, self.filename, self.lineno))

    @property
    def regular_name(self):
        name, module = self.name, self.module
        if name and module:
            return ':'.join([module, name])
        return name or module

    @property
    def deep_count(self):
        return self.own_count + sum(stat.deep_count for stat in self)

    @property
    def own_time(self):
        sub_time = sum(stat.deep_time for stat in self)
        return max(0., self.deep_time - sub_time)

    @property
    def deep_time_per_call(self):
        try:
            return self.deep_time / self.deep_count
        except ZeroDivisionError:
            return 0.0

    @property
    def own_time_per_call(self):
        try:
            return self.own_time / self.own_count
        except ZeroDivisionError:
            return 0.0

    def sorted(self, order=by_deep_time):
        return sorted(self, key=order)

    def __iter__(self):
        """Override it to walk child stats."""
        return iter(())

    def __len__(self):
        """Override it to count child stats."""
        return 0

    def __getstate__(self):
        return tuple(getattr(self, attr) for attr in self._state_slots)

    def __setstate__(self, state):
        for attr, val in zip(self._state_slots, state):
            setattr(self, attr, val)

    def __repr__(self):
        # format name
        regular_name = self.regular_name
        name_string = '' if regular_name else "'{0}'".format(regular_name)
        # format count
        deep_count = self.deep_count
        if self.own_count == deep_count:
            count_string = str(self.own_count)
        else:
            count_string = '{0}/{1}'.format(self.own_count, deep_count)
        # format time
        time_string = '{0:.6f}/{1:.6f}'.format(self.own_time, self.deep_time)
        # join all
        class_name = type(self).__name__
        return ('<{0} {1}count={2} time={3}>'
                ''.format(class_name, name_string, count_string, time_string))


class Statistics(Statistic):
    """Thr root statistic of the statistics tree."""

    _state_slots = ['cpu_time', 'wall_time']

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
    def deep_time(self):
        return self.wall_time

    @deep_time.setter
    def deep_time(self, wall_time):
        self.wall_time = wall_time

    @property
    def own_time(self):
        return self.cpu_time

    @own_time.setter
    def own_time(self, cpu_time):
        self.cpu_time = cpu_time

    def clear(self):
        self.children.clear()
        cls = type(self)
        self.own_count = cls.own_count
        self.cpu_time = cls.cpu_time
        self.wall_time = cls.wall_time
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


class RecordingStatistic(Statistic):
    """Recordig statistic measures execution time of a code."""

    _state_slots = None

    def __init__(self, code=None):
        super(RecordingStatistic, self).__init__()
        self.code = code
        self.children = {}
        self._times_entered = {}
        self.lock = RLock()

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

    def record_call(self):
        with self.lock:
            self.own_count += 1

    def record_entering(self, time, frame_key=None):
        with self.lock:
            self._times_entered[frame_key] = time
            self.record_call()

    def record_leaving(self, time, frame_key=None):
        with self.lock:
            time_entered = self._times_entered.pop(frame_key)
            time_elapsed = time - time_entered
            self.deep_time += max(0, time_elapsed)

    def clear(self):
        with self.lock:
            self.code = None
            self.children.clear()
            cls = type(self)
            self.own_count = cls.own_count
            self.deep_time = cls.deep_time
            self._times_entered.clear()

    def get_child(self, code):
        with self.lock:
            return self.children[code]

    def add_child(self, code, stat):
        with self.lock:
            self.children[code] = stat

    def remove_child(self, code):
        with self.lock:
            del self.children[code]

    def discard_child(self, code):
        with self.lock:
            self.children.pop(code, None)

    def ensure_child(self, code, adding_stat_class=None):
        with self.lock:
            try:
                return self.get_child(code)
            except KeyError:
                stat_class = adding_stat_class or type(self)
                stat = stat_class(code)
                self.add_child(code, stat)
                return stat

    def __iter__(self):
        return itervalues(self.children)

    def __len__(self):
        return len(self.children)

    def __contains__(self, code):
        return code in self.children

    def __getstate__(self):
        raise TypeError('Cannot dump recording statistic')


class RecordingStatistics(RecordingStatistic, Statistics):
    """Thr root statistic of the recording statistics tree."""

    _state_slots = None

    wall = time.time

    record_entering = failure('record_entering')
    record_leaving = failure('record_leaving')

    def record_starting(self, time):
        self._cpu_time_started = time
        self._wall_time_started = self.wall()

    def record_stopping(self, time):
        try:
            self.cpu_time = max(0, time - self._cpu_time_started)
            self.wall_time = max(0, self.wall() - self._wall_time_started)
        except AttributeError:
            raise RuntimeError('Starting does not recorded')
        del self._cpu_time_started
        del self._wall_time_started


class VoidRecordingStatistic(RecordingStatistic):
    """Statistic for an absent frame."""

    _state_slots = None

    clear = failure('clear')

    @property
    def deep_time(self):
        return sum(stat.deep_time for stat in self)

    def record_entering(self, time, frame=None):
        pass

    def record_leaving(self, time, frame=None):
        pass


class FrozenStatistic(Statistic):
    """Frozen :class:`Statistic` to serialize by Pickle."""

    _state_slots = ['name', 'filename', 'lineno', 'module',
                    'own_count', 'deep_time', 'children']

    def __init__(self, stat):
        super(FrozenStatistic, self).__init__(stat)
        self.own_count = stat.own_count
        self.deep_time = stat.deep_time
        self.children = self._freeze_children(stat)

    @classmethod
    def _freeze_children(cls, stat):
        with stat.lock:
            return [cls(s) for s in stat]

    def __iter__(self):
        return iter(self.children)

    def __len__(self):
        return len(self.children)


class FrozenStatistics(FrozenStatistic, Statistics):
    """Frozen :class:`Statistics` to serialize by Pickle."""

    _state_slots = ['cpu_time', 'wall_time', 'children']

    def __init__(self, stats):
        Statistic.__init__(self)
        self.cpu_time = stats.cpu_time
        self.wall_time = stats.wall_time
        self.children = FrozenStatistic._freeze_children(stats)


class FlatStatistic(Statistic):

    _state_slots = ['name', 'filename', 'lineno', 'module',
                    'own_count', 'deep_time', 'own_time']

    own_time = 0.0


class FlatStatistics(Statistics):

    _state_slots = ['cpu_time', 'wall_time', 'children']

    @classmethod
    def _flatten_stats(cls, stats, registry=None):
        if registry is None:
            registry = {}
            defaultdict(FlatStatistic)
        for stat in stats:
            try:
                flatten_stat = registry[stat.regular_name]
            except KeyError:
                flatten_stat = FlatStatistic(stat)
                registry[stat.regular_name] = flatten_stat
            for attr in ['own_count', 'deep_time', 'own_time']:
                value = getattr(flatten_stat, attr) + getattr(stat, attr)
                setattr(flatten_stat, attr, value)
            cls._flatten_stats(stat, registry=registry)
        return registry.values()

    def __init__(self, stats):
        Statistic.__init__(self)
        self.cpu_time = stats.cpu_time
        self.wall_time = stats.wall_time
        self.children = self._flatten_stats(stats)

    def __iter__(self):
        return iter(self.children)

    def __len__(self):
        return len(self.children)
