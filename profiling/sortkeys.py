# -*- coding: utf-8 -*-
"""
    profiling.sortkeys
    ~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import


__all__ = ['by_name', 'by_module', 'by_calls', 'by_total_time', 'by_own_time',
           'by_total_time_per_call', 'by_own_time_per_call']


class SortKey(object):

    def __init__(self, func):
        super(SortKey, self).__init__()
        self.func = func

    def __call__(self, stat):
        return self.func(stat)

    def __invert__(self):
        cls = type(self)
        return cls(lambda stat: -self.func(stat))


by_name = SortKey(lambda stat: stat.name)
by_module = SortKey(lambda stat: stat.module)
by_calls = SortKey(lambda stat: stat.calls)
by_total_time = SortKey(lambda stat: stat.total_time)
by_own_time = SortKey(lambda stat: stat.own_time)
by_total_time_per_call = SortKey(lambda stat: stat.total_time_per_call)
by_own_time_per_call = SortKey(lambda stat: stat.own_time_per_call)
