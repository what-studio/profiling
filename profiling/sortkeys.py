# -*- coding: utf-8 -*-
"""
    profiling.sortkeys
    ~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import


__all__ = ['by_name', 'by_count', 'by_total_time', 'by_own_time',
           'by_total_time_per_call', 'by_own_time_per_call']


by_name = lambda stat: stat.name
by_count = lambda stat: stat.count
by_total_time = lambda stat: stat.total_time
by_own_time = lambda stat: stat.own_time
by_total_time_per_call = lambda stat: stat.total_time_per_call
by_own_time_per_call = lambda stat: stat.own_time_per_call
