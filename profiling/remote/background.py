# -*- coding: utf-8 -*-
"""
    profiling.remote.background
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    A profiling server in a background thread starts profiling in the main
    thread.

"""
from __future__ import absolute_import
import os
import signal
import threading

from . import INTERVAL, LOG, PICKLE_PROTOCOL
from .select import profiling_server
from ..profiler import Profiler


__all__ = ['BackgroundProfiler', 'start_profiling_server']


class BackgroundProfiler(Profiler):

    def __init__(self, timer=None, top_frame=None, top_code=None,
                 start_signo=signal.SIGUSR1, stop_signo=signal.SIGUSR2):
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


def start_profiling_server(listener, profiler=None, log=LOG, interval=INTERVAL,
                           pickle_protocol=PICKLE_PROTOCOL):
    """Runs :func:`profiling.remote.select.profiling_server` in a background
    thread.

    This function is coupled with :class:`BackgroundProfiler` for starting main
    thread profiling at the background thread.  It registers two signal
    handlers by :meth:`BackgroundProfiler.prepare`.
    """
    if profiler is None:
        profiler = BackgroundProfiler()
    elif not isinstance(profiler, BackgroundProfiler):
        errmsg = 'start_profiling_server() accepts only BackgroundProfiler.'
        raise TypeError(errmsg)
    profiler.prepare()
    args = (listener, profiler, log, interval, pickle_protocol)
    thread = threading.Thread(target=profiling_server, args=args)
    thread.daemon = True
    thread.start()
    return thread
