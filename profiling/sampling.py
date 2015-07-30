# -*- coding: utf-8 -*-
"""
    profiling.sampling
    ~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
import os
import signal
import sys
import multiprocessing
import time

import six.moves._thread as _thread

from .profiler import Profiler
from .stats import RecordingStatistic, RecordingStatistics
from .utils import frame_stack


__all__ = ['SamplingProfiler']


class SamplingProfiler(Profiler):

    stats_class = RecordingStatistics

    rate = 100
    signum = signal.SIGALRM

    main_thread_id = _thread.get_ident()

    def __init__(self, top_frame=None, top_code=None, rate=None, signum=None):
        super(SamplingProfiler, self).__init__(top_frame, top_code)
        if rate is not None:
            self.rate = rate
        if signum is not None:
            self.signum = signum

    def handle_signal(self, signum, frame):
        frames = sys._current_frames()
        # replace frame of the main thread with the interrupted frame.
        frames[self.main_thread_id] = frame
        for frame_ in frames.values():
            self.sample(frame_)

    def sample(self, frame):
        """Samples the given frame."""
        frames = frame_stack(frame, self.top_frame, self.top_code)
        frames.pop()
        if not frames:
            return
        # count function call.
        parent_stat = self.stats
        for f in frames:
            parent_stat = parent_stat.ensure_child(f.f_code)
        code = frame.f_code
        try:
            stat = parent_stat.get_child(code)
        except KeyError:
            stat = RecordingStatistic(code)
            parent_stat.add_child(code, stat)
        stat.record_call()

    def sampler(self, pid):
        """Activates :meth:`sample` of the process periodically by signal.  It
        would be run on a subprocess.
        """
        interval = 1. / self.rate
        while True:
            time.sleep(interval)
            try:
                os.kill(pid, self.signum)
            except OSError:
                break

    def run(self):
        prev_handler = signal.signal(self.signum, self.handle_signal)
        # spawn a sampling process.
        sampling = multiprocessing.Process(target=self.sampler,
                                           args=(os.getpid(),))
        sampling.daemon = True
        sampling.start()
        self.stats.record_starting(time.clock())
        yield
        self.stats.record_stopping(time.clock())
        sampling.terminate()
        signal.signal(signal.SIGALRM, prev_handler)
