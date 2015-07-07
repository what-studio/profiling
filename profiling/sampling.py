# -*- coding: utf-8 -*-
"""
    profiling.sampling
    ~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
import os
import signal
import threading
import time

from .profiler import Profiler
from .stats import RecordingStatistic


__all__ = ['SamplingProfiler']


class SignalThread(threading.Thread):

    def __init__(self, signum=signal.SIGALRM, interval=0.01):
        threading.Thread.__init__(self)
        self.signum = signum
        self.interval = interval
        self.pid = os.getpid()
        self.stopper = threading.Event()
        self.daemon = True

    def send_signal(self):
        if os is not None:
            os.kill(self.pid, self.signum)

    def run(self):
        while not self.stopper.wait(self.interval):
            self.send_signal()
            if self.stopper.wait is None:
                break

    def stop(self):
        self.stopper.set()


class SamplingProfiler(Profiler):

    signum = signal.SIGALRM

    def handle_signal(self, signum, frame):
        frame_stack = self._frame_stack(frame)
        frame_stack.pop()
        if not frame_stack:
            return
        # count function call.
        parent_stat = self.stats
        for f in frame_stack:
            parent_stat = parent_stat.ensure_child(f.f_code)
        code = frame.f_code
        try:
            stat = parent_stat.get_child(code)
        except KeyError:
            stat = RecordingStatistic(code)
            parent_stat.add_child(code, stat)
        stat.record_call()

    def start(self):
        self._running = True
        self.prev_handler = signal.signal(self.signum, self.handle_signal)
        self.signal_thread = SignalThread(self.signum)
        self.signal_thread.start()
        self.stats.record_starting(time.clock())

    def stop(self):
        self.stats.record_stopping(time.clock())
        signal.signal(signal.SIGALRM, self.prev_handler)
        self.signal_thread.stop()
        self._running = False
