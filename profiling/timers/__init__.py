# -*- coding: utf-8 -*-
"""
    profiling.timers
    ~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
import time


__all__ = ['Timer', 'ContextualTimer']


class Timer(object):

    clock = time.clock

    def __call__(self):
        return self.clock()

    def start(self):
        pass

    def stop(self):
        pass


class ContextualTimer(Timer):

    def __init__(self):
        super(ContextualTimer, self).__init__()
        self.contextual_times = {}

    def __call__(self, context=None):
        context = self.detect_context(context)
        paused_at, resumed_at = self.contextual_times.get(context, (0, 0))
        if resumed_at is None:  # paused
            return paused_at
        return paused_at + self.clock() - resumed_at

    def pause(self, context=None):
        context = self.detect_context(context)
        self.contextual_times[context] = (self(context), None)

    def resume(self, context=None):
        context = self.detect_context(context)
        paused_at, __ = self.contextual_times.get(context, (0, 0))
        self.contextual_times[context] = (paused_at, self.clock())

    def detect_context(self, context=None):
        raise NotImplementedError('detect_context() should be implemented')
