# -*- coding: utf-8 -*-
"""
    profiling.stats
    ~~~~~~~~~~~~~~~

    Statistic classes.

"""
from __future__ import absolute_import, division
import inspect
from threading import RLock

from six import itervalues

from .sortkeys import by_deep_time


__all__ = ['Statistic', 'RecordingStatistic', 'VoidRecordingStatistic',
           'FrozenStatistic']


def failure(funcname, message='{class} not allow {func}.', exctype=TypeError):
    """Generates a method which raises an exception."""
    def func(self, *args, **kwargs):
        fmtopts = {'func': funcname, 'obj': self, 'class': type(self).__name__}
        raise exctype(message.format(**fmtopts))
    func.__name__ = funcname
    return func


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
            return self.deep_time / self.own_count
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
        name_string = "'{0}' ".format(regular_name) if regular_name else ''
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


class RecordingStatistic(Statistic):
    """Recordig statistic measures execution time of a code."""

    _state_slots = None

    def __init__(self, code):
        super(RecordingStatistic, self).__init__()
        self.code = code
        self.children = {}
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

    def clear(self):
        with self.lock:
            self.code = None
            self.children.clear()
            cls = type(self)
            self.own_count = cls.own_count
            self.deep_time = cls.deep_time

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


class VoidRecordingStatistic(RecordingStatistic):
    """Statistic for an absent frame."""

    _state_slots = None

    clear = failure('clear')

    @property
    def deep_time(self):
        return sum(stat.deep_time for stat in self)


class FrozenStatistic(Statistic):
    """Frozen :class:`Statistic` to serialize by Pickle."""

    _state_slots = ['name', 'filename', 'lineno', 'module',
                    'own_count', 'deep_time', 'children']

    def __init__(self, stat, slots=('own_count', 'deep_time')):
        super(FrozenStatistic, self).__init__(stat)
        for attr in slots:
            setattr(self, attr, getattr(stat, attr))
        self.children = self._freeze_children(stat)

    @classmethod
    def _freeze_children(cls, stat):
        with stat.lock:
            return [cls(s) for s in stat]

    def __iter__(self):
        return iter(self.children)

    def __len__(self):
        return len(self.children)
