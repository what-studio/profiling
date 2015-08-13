# -*- coding: utf-8 -*-
"""
    profiling.sampling
    ~~~~~~~~~~~~~~~~~~

    Profiles statistically by ``signal.ITIMER_REAL``.

"""
from __future__ import absolute_import
import time

from .. import sortkeys
from ..profiler import Profiler
from ..stats import RecordingStatistic, VoidRecordingStatistic
from ..utils import frame_stack
from ..viewer import StatisticsTable, fmt
from .samplers import Sampler, ItimerSampler


__all__ = ['SamplingProfiler', 'SamplingStatisticsTable']


DEFAULT_SAMPLER_CLASS = ItimerSampler


class SamplingStatisticsTable(StatisticsTable):

    columns = [
        ('FUNCTION', 'left', ('weight', 1), sortkeys.by_function),
        ('OWN', 'right', (6,), sortkeys.by_own_count),
        ('%', 'left', (4,), None),
        ('DEEP', 'right', (6,), sortkeys.by_deep_count),
        ('%', 'left', (4,), None),
    ]
    order = sortkeys.by_deep_count

    def make_cells(self, node, stat, stats):
        yield fmt.make_stat_text(stat)
        yield fmt.make_int_or_na_text(stat.own_count)
        yield fmt.make_percent_text(stat.own_count, stats.deep_count)
        yield fmt.make_int_or_na_text(stat.deep_count)
        yield fmt.make_percent_text(stat.deep_count, stats.deep_count)


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
        # count function call.
        parent_stat = self.stats
        for f in frames:
            parent_stat = \
                parent_stat.ensure_child(f.f_code, VoidRecordingStatistic)
        code = frame.f_code
        stat = parent_stat.ensure_child(code, RecordingStatistic)
        stat.record_call()

    def run(self):
        self.sampler.start(self)
        self.stats.record_starting(time.clock())
        yield
        self.stats.record_stopping(time.clock())
        self.sampler.stop()
