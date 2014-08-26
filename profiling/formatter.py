# -*- coding: utf-8 -*-
"""
    profiling.formatter
    ~~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
import sys

from .sortkeys import by_total_time


__all__ = ['Formatter']


class Formatter(object):

    def __init__(self, stat):
        super(Formatter, self).__init__()
        self.stat = stat

    def format_stat(self, stat):
        return '{0:.2%} {1:.6f}/{2:.6f} {3}'.format(
            stat.total_time / self.stat.total_time, stat.own_time,
            stat.total_time, stat.name)

    def format_stats(self, order=by_total_time, max_depth=3,
                     _stat=None, _depth=0, _buf=None):
        if _stat is None:
            _stat = self.stat
        if _buf is None:
            _buf = [self.format_stat(_stat)]
        for stat in _stat.sorted(order):
            indent = ' ' * (_depth * 2)
            _buf.append('{0}- {1}'.format(indent, self.format_stat(stat)))
            if _depth >= max_depth:
                continue
            self.format_stats(order, max_depth, stat, _depth + 1, _buf)
        return _buf

    def print_stats(self, stream=sys.stdout, order=by_total_time, max_depth=3):
        stream.write('\n'.join(self.format_stats(order, max_depth)))
        stream.write('\n')
        stream.flush()
