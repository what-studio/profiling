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


__all__ = ['BackgroundProfiler']


START_SIGNO = signal.SIGUSR1
STOP_SIGNO = signal.SIGUSR2


class BackgroundProfiler(Profiler):

    def __init__(self, timer=None, top_frame=None, top_code=None,
                 start_signo=START_SIGNO, stop_signo=STOP_SIGNO):
        super(BackgroundProfiler, self).__init__(timer, top_frame, top_code)
        self.event = threading.Event()
        self.start_signo = start_signo
        self.stop_signo = stop_signo

    def prepare(self):
        """Registers signal handlers to start and/or stop the profiler at the
        background thread.  So this function must be called at the main thread.
        """
        signal.signal(self.start_signo, self._start_signal_handler)
        signal.signal(self.stop_signo, self._stop_signal_handler)

    def start(self):
        self.event.clear()
        os.kill(os.getpid(), self.start_signo)
        self.event.wait()

    def stop(self):
        self.event.clear()
        os.kill(os.getpid(), self.stop_signo)
        self.event.wait()

    def _start_signal_handler(self, signo, frame):
        super(BackgroundProfiler, self).start()
        self.event.set()

    def _stop_signal_handler(self, signo, frame):
        super(BackgroundProfiler, self).stop()
        self.event.set()
