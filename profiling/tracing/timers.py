# -*- coding: utf-8 -*-
"""
   profiling.tracing.timers
   ~~~~~~~~~~~~~~~~~~~~~~~~

   :copyright: (c) 2014-2017, What! Studio
   :license: BSD, see LICENSE for more details.

"""
from __future__ import absolute_import

import time

from profiling.utils import lazy_import, Runnable, thread_clock


__all__ = ['Timer', 'ContextualTimer', 'ThreadTimer', 'GreenletTimer']


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
        if context is None:
            context = self.detect_context()
        paused_at, resumed_at = self._contextual_times.get(context, (0, 0))
        if resumed_at is None:  # paused
            return paused_at
        return paused_at + self.clock() - resumed_at

    def pause(self, context=None):
        if context is None:
            context = self.detect_context()
        self._contextual_times[context] = (self(context), None)

    def resume(self, context=None):
        if context is None:
            context = self.detect_context()
        paused_at, __ = self._contextual_times.get(context, (0, 0))
        self._contextual_times[context] = (paused_at, self.clock())

    def detect_context(self):
        raise NotImplementedError('detect_context() should be implemented')


class ThreadTimer(Timer):
    """A timer to get CPU time per thread.  Python 3.3 or later uses the
    built-in :mod:`time` module.  Earlier Python versions requires `Yappi`_ to
    be installed.

    .. _Yappi: https://code.google.com/p/yappi/

    """

    def __call__(self):
        return thread_clock()


class GreenletTimer(ContextualTimer):
    """A timer to get CPU time per greenlet."""

    greenlet = lazy_import('greenlet')

    def detect_context(self):
        if self.greenlet:
            return id(self.greenlet.getcurrent())

    def _trace(self, event, args):
        origin, target = args
        self.pause(id(origin))
        self.resume(id(target))

    def run(self, profiler):
        self.greenlet.settrace(self._trace)
        yield
        self.greenlet.settrace(None)
