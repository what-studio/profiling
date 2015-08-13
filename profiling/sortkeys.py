# -*- coding: utf-8 -*-
"""
    profiling.sortkeys
    ~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import


__all__ = ['by_name', 'by_module', 'by_deep_count', 'by_own_count',
           'by_deep_time', 'by_own_time', 'by_deep_time_per_call',
           'by_own_time_per_call']


class SortKey(object):

    def __init__(self, func):
        super(SortKey, self).__init__()
        self.func = func

    def __call__(self, stat):
        return self.func(stat)

    def __invert__(self):
        cls = type(self)
        return cls(lambda stat: -self.func(stat))


def _by_deep_time_per_call(stat):
    return -stat.deep_time_per_call if stat.deep_count else -stat.deep_time


def _by_own_time_per_call(stat):
    return (-stat.own_time_per_call if stat.own_count else -stat.own_time,
            _by_deep_time_per_call(stat))


#: Sorting by name in ascending order.
by_name = SortKey(lambda stat: stat.name)

#: Sorting by module in ascending order.
by_module = SortKey(lambda stat: stat.module)

#: Sorting by module and name in ascending order.
by_function = SortKey(lambda stat: (stat.module, stat.name))

#: Sorting by number of inclusive count in descending order.
by_deep_count = SortKey(lambda stat: -stat.deep_count)

#: Sorting by number of exclusive count in descending order.
by_own_count = SortKey(lambda stat: -stat.own_count)

#: Sorting by inclusive elapsed time in descending order.
by_deep_time = SortKey(lambda stat: -stat.deep_time)

#: Sorting by exclusive elapsed time in descending order.
by_own_time = SortKey(lambda stat: (-stat.own_time, -stat.deep_time))

#: Sorting by inclusive elapsed time per call in descending order.
by_deep_time_per_call = SortKey(_by_deep_time_per_call)

#: Sorting by exclusive elapsed time per call in descending order.
by_own_time_per_call = SortKey(_by_own_time_per_call)
