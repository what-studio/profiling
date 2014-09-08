# -*- coding: utf-8 -*-
"""
    profiling.timers.greenlet
    ~~~~~~~~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import

from . import ContextualTimer


__all__ = ['GreenletTimer']


class GreenletTimer(ContextualTimer):

    greenlet = None

    def __init__(self):
        self.greenlet = __import__('greenlet')
        super(GreenletTimer, self).__init__()

    def detect_context(self, context=None):
        if context is None and self.greenlet:
            context = id(self.greenlet.getcurrent())
        return context

    def start(self):
        self.greenlet.settrace(self._trace)

    def stop(self):
        self.greenlet.settrace(None)

    def _trace(self, event, args):
        origin, target = args
        self.pause(id(origin))
        self.resume(id(target))
