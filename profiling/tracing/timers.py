# -*- coding: utf-8 -*-
"""
    profiling.tracing.timers
    ~~~~~~~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
import sys
import time

from ..utils import Runnable, lazy_import


__all__ = ['Timer', 'ContextualTimer', 'ThreadTimer', 'YappiTimer',
           'GreenletTimer']


class Timer(Runnable):
    """The basic timer."""

    #: The raw function to get the CPU time.
    clock = time.clock

    def __call__(self):
        return self.clock()

    def run(self, profiler):
        yield


class ContextualTimer(Timer):

    def __new__(cls, *args, **kwargs):
        timer = super(ContextualTimer, cls).__new__(cls, *args, **kwargs)
        timer._contextual_times = {}
        return timer

    def __call__(self, context=None):
        context = self.detect_context(context)
        paused_at, resumed_at = self._contextual_times.get(context, (0, 0))
        if resumed_at is None:  # paused
            return paused_at
        return paused_at + self.clock() - resumed_at

    def pause(self, context=None):
        context = self.detect_context(context)
        self._contextual_times[context] = (self(context), None)

    def resume(self, context=None):
        context = self.detect_context(context)
        paused_at, __ = self._contextual_times.get(context, (0, 0))
        self._contextual_times[context] = (paused_at, self.clock())

    def detect_context(self, context=None):
        raise NotImplementedError('detect_context() should be implemented')


class ThreadTimer(Timer):
    """A timer to get CPU time per thread.  Python 3.3 or later required."""

    if sys.version_info < (3, 3):
        def __init__(self):
            raise RuntimeError('Python 3.3 or later required.  '
                               'Use YappiTimer instead.')

    def __call__(self):
        return time.clock_gettime(time.CLOCK_THREAD_CPUTIME_ID)


class YappiTimer(Timer):
    """A timer to get CPU time per thread using `Yappi`_'s timer.

    .. _Yappi: https://code.google.com/p/yappi/

    """

    yappi = lazy_import('yappi')

    def __call__(self):
        return self.yappi.get_clock_time()


class GreenletTimer(ContextualTimer):

    greenlet = lazy_import('greenlet')

    def detect_context(self, context=None):
        if context is None and self.greenlet:
            context = id(self.greenlet.getcurrent())
        return context

    def _trace(self, event, args):
        origin, target = args
        self.pause(id(origin))
        self.resume(id(target))

    def run(self, profiler):
        self.greenlet.settrace(self._trace)
        yield
        self.greenlet.settrace(None)
