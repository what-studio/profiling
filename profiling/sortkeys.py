# -*- coding: utf-8 -*-
"""
    profiling.sortkeys
    ~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import


__all__ = ['by_name', 'by_module', 'by_total_calls', 'by_own_calls',
           'by_total_time', 'by_own_time', 'by_total_time_per_call',
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


def _by_total_time_per_call(stat):
    return -stat.total_time_per_call if stat.total_calls else -stat.total_time


def _by_own_time_per_call(stat):
    return (-stat.own_time_per_call if stat.own_calls else -stat.own_time,
            _by_total_time_per_call(stat))


#: Sorting by name in ascending order.
by_name = SortKey(lambda stat: stat.name)

#: Sorting by module in ascending order.
by_module = SortKey(lambda stat: stat.module)

#: Sorting by module and name in ascending order.
by_function = SortKey(lambda stat: (stat.module, stat.name))

#: Sorting by number of inclusive calls in descending order.
by_total_calls = SortKey(lambda stat: -stat.total_calls)

#: Sorting by number of exclusive calls in descending order.
by_own_calls = SortKey(lambda stat: -stat.own_calls)

#: Sorting by inclusive elapsed time in descending order.
by_total_time = SortKey(lambda stat: -stat.total_time)

#: Sorting by exclusive elapsed time in descending order.
by_own_time = SortKey(lambda stat: (-stat.own_time, -stat.total_time))

#: Sorting by inclusive elapsed time per call in descending order.
by_total_time_per_call = SortKey(_by_total_time_per_call)

#: Sorting by exclusive elapsed time per call in descending order.
by_own_time_per_call = SortKey(_by_own_time_per_call)
