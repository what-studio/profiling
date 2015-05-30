# -*- coding: utf-8 -*-
"""
    profiling.remote.background
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Utilities to run a profiler in a background thread.

"""
from __future__ import absolute_import
import os
import signal
import threading

from ..profiler import Profiler


__all__ = ['SIGNUM', 'BackgroundProfiler']


SIGNUM = signal.SIGUSR2


class BackgroundProfilerTrigger(object):

    def __init__(self, profiler, signum=SIGNUM):
        self.profiler = profiler
        self.signum = signum
        self.event = threading.Event()

    def prepare(self):
        """Registers :meth:`_signal_handler` as a signal handler to start
        and/or stop the profiler from the background thread.  So this function
        must be called at the main thread.
        """
        signal.signal(self.signum, self._signal_handler)

    def start(self):
        self._send_signal()

    def stop(self):
        self._send_signal()

    def clear(self):
        self.profiler.clear()

    def result(self):
        return self.profiler.result()

    def _send_signal(self):
        self.event.clear()
        os.kill(os.getpid(), self.signum)
        self.event.wait()

    def _signal_handler(self, signum, frame):
        if self.profiler.is_running():
            self.profiler.stop()
        else:
            self.profiler.start()
        self.event.set()


class BackgroundProfiler(Profiler):

    def __init__(self, timer=None, top_frame=None, top_code=None,
                 signum=SIGNUM):
        super(BackgroundProfiler, self).__init__(timer, top_frame, top_code)
        self.event = threading.Event()
        self.signum = signum

    def prepare(self):
        """Registers :meth:`_signal_handler` as a signal handler to start
        and/or stop the profiler from the background thread.  So this function
        must be called at the main thread.
        """
        signal.signal(self.signum, self._signal_handler)

    def start(self):
        self._send_signal()

    def stop(self):
        self._send_signal()

    def _send_signal(self):
        self.event.clear()
        os.kill(os.getpid(), self.signum)
        self.event.wait()

    def _signal_handler(self, signum, frame):
        base = super(BackgroundProfiler, self)
        if self.is_running():
            base.stop()
        else:
            base.start()
        self.event.set()
