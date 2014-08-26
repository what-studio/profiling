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

    def __init__(self, profiler):
        super(Formatter, self).__init__()
        self.profiler = profiler

    def format_stats(self, stat=None, order=by_total_time, depth=0, buf=None):
        if stat is None:
            stat = self.profiler.stat
        if buf is None:
            buf = []
        for child_stat in stat.sorted(order):
            indent = ' ' * (depth * 2)
            line = indent + '- {0:.2%} {1:.6f}/{2:.6f} {3}'.format(
                child_stat.total_time / self.profiler.stat.total_time,
                child_stat.own_time, child_stat.total_time,
                child_stat.name)
            buf.append(line)
            if depth > 3:
                continue
            self.format_stats(child_stat, order, depth + 1, buf)
        return buf

    def print_stats(self, stream=sys.stdout, stat=None, order=by_total_time):
        stream.write('\n'.join(self.format_stats(stat, order)).encode('utf-8'))
