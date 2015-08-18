# -*- coding: utf-8 -*-
"""
    profiling.stats
    ~~~~~~~~~~~~~~~

    Statistics classes.

"""
from __future__ import absolute_import, division
import inspect
from threading import RLock

from six import itervalues

from .sortkeys import by_deep_time


__all__ = ['Statistics', 'RecordingStatistics', 'VoidRecordingStatistics',
           'FrozenStatistics']


def failure(funcname, message='{class} not allow {func}.', exctype=TypeError):
    """Generates a method which raises an exception."""
    def func(self, *args, **kwargs):
        fmtopts = {'func': funcname, 'obj': self, 'class': type(self).__name__}
        raise exctype(message.format(**fmtopts))
    func.__name__ = funcname
    return func


class Statistics(object):
    """Statistics of a function."""

    _state_slots = ['name', 'filename', 'lineno', 'module',
                    'own_count', 'deep_time']

    name = None
    filename = None
    lineno = None
    module = None

    #: The inclusive execution count.
    own_count = 0

    #: The exclusive execution time.
    deep_time = 0.0

    def __init__(self, stats=None, name=None, filename=None, lineno=None,
                 module=None):
        if stats is not None:
            assert name is filename is lineno is module is None
            name = stats.name
            filename = stats.filename
            lineno = stats.lineno
            module = stats.module
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
        return self.own_count + sum(stats.deep_count for stats in self)

    @property
    def own_time(self):
        sub_time = sum(stats.deep_time for stats in self)
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


class RecordingStatistics(Statistics):
    """Recordig statistics measures execution time of a code."""

    _state_slots = None

    def __init__(self, code=None):
        super(RecordingStatistics, self).__init__()
        self.code = code
        self.lock = RLock()
        self._children = {}

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
            self._children.clear()
            cls = type(self)
            self.own_count = cls.own_count
            self.deep_time = cls.deep_time

    def get_child(self, code):
        with self.lock:
            return self._children[code]

    def add_child(self, code, stats):
        with self.lock:
            self._children[code] = stats

    def remove_child(self, code):
        with self.lock:
            del self._children[code]

    def discard_child(self, code):
        with self.lock:
            self._children.pop(code, None)

    def ensure_child(self, code, adding_stat_class=None):
        with self.lock:
            try:
                return self.get_child(code)
            except KeyError:
                stat_class = adding_stat_class or type(self)
                stats = stat_class(code)
                self.add_child(code, stats)
                return stats

    def __iter__(self):
        return itervalues(self._children)

    def __len__(self):
        return len(self._children)

    def __contains__(self, code):
        return code in self._children

    def __getstate__(self):
        raise TypeError('Cannot dump recording statistics')


class VoidRecordingStatistics(RecordingStatistics):
    """Statistics for an absent frame."""

    _state_slots = None

    clear = failure('clear')

    @property
    def deep_time(self):
        return sum(stats.deep_time for stats in self)


class FrozenStatistics(Statistics):
    """Frozen :class:`Statistics` to serialize by Pickle."""

    _state_slots = ['name', 'filename', 'lineno', 'module',
                    'own_count', 'deep_time', '_children']

    def __init__(self, stats, slots=('own_count', 'deep_time')):
        super(FrozenStatistics, self).__init__(stats)
        for attr in slots:
            setattr(self, attr, getattr(stats, attr))
        self._children = self._freeze_children(stats)

    @classmethod
    def _freeze_children(cls, stats):
        with stats.lock:
            return [cls(s) for s in stats]

    def __iter__(self):
        return iter(self._children)

    def __len__(self):
        return len(self._children)
