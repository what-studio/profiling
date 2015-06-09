# -*- coding: utf-8 -*-
"""
    profiling.sampling
    ~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
import os
import signal
import threading

from .profiler import Profiler


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
        try:
            os.kill(self.pid, self.signum)
        except AttributeError:
            pass

    def run(self):
        while not self.stopper.wait(self.interval):
            self.send_signal()

    def stop(self):
        self.stopper.set()


class SamplingProfiler(Profiler):

    signum = signal.SIGALRM

    def handle_signal(self, signum, frame):
        self._profile(frame, 'call', None)
        self._profile(frame, 'return', None)

    def start(self):
        self.prev_handler = signal.signal(self.signum, self.handle_signal)
        self.signal_thread = SignalThread(self.signum)
        self.signal_thread.start()

    def stop(self):
        signal.signal(signal.SIGALRM, self.prev_handler)
        self.signal_thread.stop()

    def _profile(self, frame, event, arg):
        """The callback function to register by :func:`sys.setprofile`."""
        if event.startswith('c_'):
            return
        frame_stack = self._frame_stack(frame)
        frame_stack.pop()
        if not frame_stack:
            return
        parent_stat = self.stats
        for f in frame_stack:
            parent_stat = parent_stat.ensure_child(f.f_code)
        code = frame.f_code
        frame_key = id(frame)
        # if c:
        #     event = event[2:]
        #     code = mock_code(arg.__name__)
        #     frame_key = id(arg)
        # record
        if event in ('call',):
            self._entered(0, code, frame_key, parent_stat)
        elif event in ('return', 'exception'):
            self._left(0, code, frame_key, parent_stat)
