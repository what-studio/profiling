# -*- coding: utf-8 -*-
"""
   profiling.sampling
   ~~~~~~~~~~~~~~~~~~

   Statistical profiling.

   :copyright: (c) 2014-2017, What! Studio
   :license: BSD, see LICENSE for more details.

"""
from __future__ import absolute_import

from profiling import sortkeys
from profiling.profiler import Profiler
from profiling.sampling.samplers import ItimerSampler, Sampler
from profiling.stats import (
    RecordingStatistics, VoidRecordingStatistics as void)
from profiling.viewer import fmt, StatisticsTable


__all__ = ['SamplingProfiler', 'SamplingStatisticsTable']


SAMPLER_CLASS = ItimerSampler


class SamplingStatisticsTable(StatisticsTable):

    columns = [
        ('FUNCTION', 'left', ('weight', 1), sortkeys.by_function),
        ('OWN', 'right', (6,), sortkeys.by_own_hits),
        ('%', 'left', (4,), None),
        ('DEEP', 'right', (6,), sortkeys.by_deep_hits),
        ('%', 'left', (4,), None),
    ]
    order = sortkeys.by_deep_hits

    def make_cells(self, node, stats):
        root_stats = node.get_root().get_value()
        yield fmt.make_stat_text(stats)
        yield fmt.make_int_or_na_text(stats.own_hits)
        yield fmt.make_percent_text(stats.own_hits, root_stats.deep_hits)
        yield fmt.make_int_or_na_text(stats.deep_hits)
        yield fmt.make_percent_text(stats.deep_hits, root_stats.deep_hits)


class SamplingProfiler(Profiler):

    table_class = SamplingStatisticsTable

    #: The frames sampler.  Usually it is an instance of :class:`profiling.
    #: sampling.samplers.Sampler`.
    sampler = None

    def __init__(self, base_frame=None, base_code=None,
                 ignored_frames=(), ignored_codes=(), sampler=None):
        sampler = sampler or SAMPLER_CLASS()
        if not isinstance(sampler, Sampler):
            raise TypeError('Not a sampler instance')
        base = super(SamplingProfiler, self)
        base.__init__(base_frame, base_code, ignored_frames, ignored_codes)
        self.sampler = sampler

    def sample(self, frame):
        """Samples the given frame."""
        frames = self.frame_stack(frame)
        if frames:
            frames.pop()
        parent_stats = self.stats
        for f in frames:
            parent_stats = parent_stats.ensure_child(f.f_code, void)
        stats = parent_stats.ensure_child(frame.f_code, RecordingStatistics)
        stats.own_hits += 1

    def run(self):
        self.sampler.start(self)
        yield
        self.sampler.stop()
