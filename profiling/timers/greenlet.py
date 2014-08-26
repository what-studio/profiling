# -*- coding: utf-8 -*-
"""
    profiling.timers.greenlet
    ~~~~~~~~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import

import greenlet

from . import ContextualTimer


__all__ = ['GreenletTimer']


class GreenletTimer(ContextualTimer):

    def detect_context(self, context=None):
        if context is None:
            context = id(greenlet.getcurrent())
        return context

    def start(self):
        greenlet.settrace(self._trace)

    def stop(self):
        greenlet.settrace(None)

    def _trace(self, event, args):
        origin, target = args
        self.pause(id(origin))
        self.resume(id(target))
