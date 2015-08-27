# -*- coding: utf-8 -*-
"""
    profiling.stats
    ~~~~~~~~~~~~~~~

    Statistics classes.

"""
from __future__ import absolute_import, division
import inspect

from six import itervalues, with_metaclass

from .sortkeys import by_deep_time


__all__ = ['Statistics', 'RecordingStatistics', 'VoidRecordingStatistics',
           'FrozenStatistics']


def stats_from_members(stats_class, members):
    stats = stats_class()
    for attr, value in zip(stats_class.__slots__, members):
        setattr(stats, attr, value)
    return stats


class default(object):

    __slots__ = ('value',)

    def __init__(self, value):
        self.value = value


class StatisticsMeta(type):

    def __new__(meta, name, bases, attrs):
        defaults = {}
        for attr in attrs.get('__slots__', ()):
            if attr not in attrs:
                continue
            elif isinstance(attrs[attr], default):
                defaults[attr] = attrs.pop(attr).value
        cls = super(StatisticsMeta, meta).__new__(meta, name, bases, attrs)
        cls.__defaults__ = defaults
        return cls

    def __call__(cls, *args, **kwargs):
        obj = super(StatisticsMeta, cls).__call__(*args, **kwargs)
        for attr, value in cls.__defaults__.items():
            if not hasattr(obj, attr):
                setattr(obj, attr, value)
        return obj


class Statistics(with_metaclass(StatisticsMeta)):
    """Statistics of a function."""

    __slots__ = ('name', 'filename', 'lineno', 'module',
                 'own_hits', 'deep_time')

    name = default(None)
    filename = default(None)
    lineno = default(None)
    module = default(None)
    #: The inclusive calling/sampling number.
    own_hits = default(0)
    #: The exclusive execution time.
    deep_time = default(0.0)

    def __init__(self, **members):
        for attr, value in members.items():
            setattr(self, attr, value)

    @property
    def regular_name(self):
        name, module = self.name, self.module
        if name and module:
            return ':'.join([module, name])
        return name or module

    @property
    def deep_hits(self):
        """The inclusive calling/sampling number.

        Calculates as sum of the own hits and deep hits of the children.
        """
        return self.own_hits + sum(stats.deep_hits for stats in self)

    @property
    def own_time(self):
        """The exclusive execution time."""
        sub_time = sum(stats.deep_time for stats in self)
        return max(0., self.deep_time - sub_time)

    @property
    def deep_time_per_call(self):
        try:
            return self.deep_time / self.own_hits
        except ZeroDivisionError:
            return 0.0

    @property
    def own_time_per_call(self):
        try:
            return self.own_time / self.own_hits
        except ZeroDivisionError:
            return 0.0

    def sorted(self, order=by_deep_time):
        return sorted(self, key=order)

    def __iter__(self):
        """Override it to walk statistics children."""
        return iter(())

    def __len__(self):
        """Override it to count statistics children."""
        return 0

    def __reduce__(self):
        """Safen for Pickle."""
        members = [getattr(self, attr) for attr in self.__slots__]
        return (stats_from_members, (self.__class__, members,))

    def __hash__(self):
        """Statistics can be a key."""
        return hash((self.name, self.filename, self.lineno))

    def __repr__(self):
        # format name
        regular_name = self.regular_name
        name_string = "'{0}' ".format(regular_name) if regular_name else ''
        # format hits
        deep_hits = self.deep_hits
        if self.own_hits == deep_hits:
            hits_string = str(self.own_hits)
        else:
            hits_string = '{0}/{1}'.format(self.own_hits, deep_hits)
        # format time
        own_time = self.own_time
        if own_time == self.deep_time:
            time_string = '{0:.6f}'.format(self.deep_time)
        else:
            time_string = '{0:.6f}/{1:.6f}'.format(own_time, self.deep_time)
        # join all
        class_name = type(self).__name__
        return ('<{0} {1}hits={2} time={3}>'
                ''.format(class_name, name_string, hits_string, time_string))


class RecordingStatistics(Statistics):
    """Recordig statistics measures execution time of a code."""

    __slots__ = ('own_hits', 'deep_time', 'code', '_children')

    own_hits = default(0)
    deep_time = default(0.0)

    def __init__(self, code=None):
        self.code = code
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

    def get_child(self, code):
        return self._children[code]

    def add_child(self, code, stats):
        self._children[code] = stats

    def remove_child(self, code):
        del self._children[code]

    def discard_child(self, code):
        self._children.pop(code, None)

    def ensure_child(self, code, adding_stat_class=None):
        stats = self._children.get(code)
        if stats is None:
            stat_class = adding_stat_class or type(self)
            stats = stat_class(code)
            self.add_child(code, stats)
        return stats

    def clear(self):
        self._children.clear()
        for attr, value in self.__defaults__.items():
            setattr(self, attr, value)

    def __iter__(self):
        return itervalues(self._children)

    def __len__(self):
        return len(self._children)

    def __contains__(self, code):
        return code in self._children

    def __reduce__(self):
        raise TypeError('Cannot dump recording statistics')


class VoidRecordingStatistics(RecordingStatistics):
    """Statistics for an absent frame."""

    __slots__ = ('code', '_children')

    _ignore = lambda x, *a, **k: None
    own_hits = property(lambda x: 0, _ignore)
    deep_time = property(lambda x: sum(s.deep_time for s in x), _ignore)
    del _ignore


class FrozenStatistics(Statistics):
    """Frozen :class:`Statistics` to serialize by Pickle."""

    __slots__ = ('name', 'filename', 'lineno', 'module',
                 'own_hits', 'deep_time', '_children')

    def __init__(self, stats=None):
        if stats is None:
            self._children = []
            return
        for attr in self.__slots__:
            try:
                value = getattr(stats, attr)
            except AttributeError:
                continue
            else:
                setattr(self, attr, value)
        self._children = self._freeze_children(stats)

    @classmethod
    def _freeze_children(cls, stats):
        children = list(stats)
        return [cls(s) for s in children]

    def __iter__(self):
        return iter(self._children)

    def __len__(self):
        return len(self._children)
