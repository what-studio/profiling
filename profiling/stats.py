# -*- coding: utf-8 -*-
"""
   profiling.stats
   ~~~~~~~~~~~~~~~

   Statistics classes.

   :copyright: (c) 2014-2017, What! Studio
   :license: BSD, see LICENSE for more details.

"""
from __future__ import absolute_import, division

from collections import deque
import inspect
import itertools

from six import itervalues, with_metaclass
from six.moves import zip

from profiling.sortkeys import by_deep_time
from profiling.utils import noop


__all__ = ['Statistics', 'RecordingStatistics', 'VoidRecordingStatistics',
           'FrozenStatistics', 'FlatFrozenStatistics']


class spread_t(object):
    __slots__ = ('flag',)
    __bool__ = __nonzero__ = lambda x: x.flag
    def clear(self):
        self.flag = False
    def __call__(self):
        self.flag = True


def spread_stats(stats, spreader=False):
    """Iterates all descendant statistics under the given root statistics.

    When ``spreader=True``, each iteration yields a descendant statistics and
    `spread()` function together.  You should call `spread()` if you want to
    spread the yielded statistics also.

    """
    spread = spread_t() if spreader else True
    descendants = deque(stats)
    while descendants:
        _stats = descendants.popleft()
        if spreader:
            spread.clear()
            yield _stats, spread
        else:
            yield _stats
        if spread:
            descendants.extend(_stats)


class default(object):

    __slots__ = ('value',)

    def __init__(self, value):
        self.value = value


class StatisticsMeta(type):

    def __new__(meta, name, bases, attrs):
        slots = attrs.get('__slots__', ())
        defaults = {}
        for attr in slots:
            if attr not in attrs:
                continue
            elif isinstance(attrs[attr], default):
                defaults[attr] = attrs.pop(attr).value
        cls = super(StatisticsMeta, meta).__new__(meta, name, bases, attrs)
        try:
            base_defaults = cls.__defaults__
        except AttributeError:
            pass
        else:
            # inherit defaults from the base classes.
            for attr in slots:
                if attr not in defaults and attr in base_defaults:
                    defaults[attr] = base_defaults[attr]
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

    def __init__(self, *args, **kwargs):
        for attr, value in zip(self.__slots__, args):
            setattr(self, attr, value)
        for attr, value in kwargs.items():
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
        hits = [self.own_hits]
        hits.extend(stats.own_hits for stats in spread_stats(self))
        return sum(hits)

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

    def __hash__(self):
        """Statistics can be a key."""
        return hash((self.name, self.filename, self.lineno))

    def __reduce__(self):
        """Freezes this statistics to safen to pack/unpack in Pickle."""
        tree = make_frozen_stats_tree(self)
        return (frozen_stats_from_tree, (tree,))

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

    @property
    def children(self):
        return list(itervalues(self._children))

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


class VoidRecordingStatistics(RecordingStatistics):
    """Statistics for an absent frame."""

    __slots__ = ('code', '_children')

    own_hits = property(lambda x: 0, noop)

    def deep_time(self):
        times = []
        for stats, spread in spread_stats(self, spreader=True):
            if isinstance(stats, VoidRecordingStatistics):
                spread()
            else:
                times.append(stats.deep_time)
        return sum(times)

    deep_time = property(deep_time, noop)


class FrozenStatistics(Statistics):
    """Frozen :class:`Statistics` to serialize by Pickle."""

    __slots__ = ('name', 'filename', 'lineno', 'module',
                 'own_hits', 'deep_time', 'children')

    def __init__(self, *args, **kwargs):
        super(FrozenStatistics, self).__init__(*args, **kwargs)
        if not hasattr(self, 'children'):
            self.children = []

    def __iter__(self):
        return iter(self.children)

    def __len__(self):
        return len(self.children)


def make_frozen_stats_tree(stats):
    """Makes a flat members tree of the given statistics.  The statistics can
    be restored by :func:`frozen_stats_from_tree`.
    """
    tree, stats_tree = [], [(None, stats)]
    for x in itertools.count():
        try:
            parent_offset, _stats = stats_tree[x]
        except IndexError:
            break
        stats_tree.extend((x, s) for s in _stats)
        members = (_stats.name, _stats.filename, _stats.lineno,
                   _stats.module, _stats.own_hits, _stats.deep_time)
        tree.append((parent_offset, members))
    return tree


def frozen_stats_from_tree(tree):
    """Restores a statistics from the given flat members tree.
    :func:`make_frozen_stats_tree` makes a tree for this function.
    """
    if not tree:
        raise ValueError('Empty tree')
    stats_index = []
    for parent_offset, members in tree:
        stats = FrozenStatistics(*members)
        stats_index.append(stats)
        if parent_offset is not None:
            stats_index[parent_offset].children.append(stats)
    return stats_index[0]


class FlatFrozenStatistics(FrozenStatistics):

    __slots__ = ('name', 'filename', 'lineno', 'module',
                 'own_hits', 'deep_hits', 'own_time', 'deep_time',
                 'children')

    own_hits = default(0)
    deep_hits = default(0)
    own_time = default(0.0)
    deep_time = default(0.0)
    children = default(())

    @classmethod
    def flatten(cls, stats):
        """Makes a flat statistics from the given statistics."""
        flat_children = {}
        for _stats in spread_stats(stats):
            key = (_stats.name, _stats.filename, _stats.lineno, _stats.module)
            try:
                flat_stats = flat_children[key]
            except KeyError:
                flat_stats = flat_children[key] = cls(*key)
            flat_stats.own_hits += _stats.own_hits
            flat_stats.deep_hits += _stats.deep_hits
            flat_stats.own_time += _stats.own_time
            flat_stats.deep_time += _stats.deep_time
        children = list(itervalues(flat_children))
        return cls(stats.name, stats.filename, stats.lineno, stats.module,
                   stats.own_hits, stats.deep_hits, stats.own_time,
                   stats.deep_time, children)
