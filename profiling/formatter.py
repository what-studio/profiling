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

    def __init__(self, stats):
        super(Formatter, self).__init__()
        self.stats = stats

    def format_stat(self, stat):
        return '{0:6.2%} {1} {2} calls, {3:.6f} total, {4:.6f} owned'.format(
            stat.total_time / self.stats.cpu_time, stat.regular_name,
            stat.calls, stat.total_time, stat.own_time)

    def format_stats(self, order=by_total_time, max_depth=3,
                     _stat=None, _depth=0, _buf=None):
        if _stat is None:
            _stat = self.stats
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


class AsciiTreeFormatter(Formatter):

    def format_stats(self, order=by_total_time, max_depth=3,
                     _stat=None, _depth=0, _buf=None):
        from asciitree import draw_tree
        if _stat is None:
            _stat = self.stat
        return [draw_tree(_stat, lambda s: s.sorted(order), self.format_stat)]
