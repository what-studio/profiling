# -*- coding: utf-8 -*-
"""
    profiling.sampling
    ~~~~~~~~~~~~~~~~~~

    Profiles statistically by ``signal.ITIMER_REAL``.

"""
from __future__ import absolute_import

from .. import sortkeys
from ..profiler import Profiler
from ..stats import RecordingStatistics, VoidRecordingStatistics
from ..utils import frame_stack
from ..viewer import StatisticsTable, fmt
from .samplers import Sampler, ItimerSampler


__all__ = ['SamplingProfiler', 'SamplingStatisticsTable']


DEFAULT_SAMPLER_CLASS = ItimerSampler


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

    def __init__(self, top_frame=None, top_code=None, sampler=None):
        sampler = sampler or DEFAULT_SAMPLER_CLASS()
        if not isinstance(sampler, Sampler):
            raise TypeError('Not a sampler instance')
        super(SamplingProfiler, self).__init__(top_frame, top_code)
        self.sampler = sampler

    def sample(self, frame):
        """Samples the given frame."""
        frames = frame_stack(frame, self.top_frame, self.top_code)
        frames.pop()
        if not frames:
            return
        void = VoidRecordingStatistics
        parent_stats = self.stats
        for f in frames:
            parent_stats = parent_stats.ensure_child(f.f_code, void)
        code = frame.f_code
        stats = parent_stats.ensure_child(code, RecordingStatistics)
        stats.own_hits += 1

    def run(self):
        self.sampler.start(self)
        yield
        self.sampler.stop()
