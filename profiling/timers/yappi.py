# -*- coding: utf-8 -*-
"""
    profiling.timers.yappi
    ~~~~~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import

import yappi

from . import Timer


__all__ = ['YappiTimer']


class YappiTimer(Timer):

    clock = staticmethod(yappi.get_clock_time)
