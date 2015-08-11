# -*- coding: utf-8 -*-
"""
    profiling.timers.thread
    ~~~~~~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
import sys
import time

from . import Timer


__all__ = ['ThreadTimer', 'YappiTimer']


class ThreadTimer(Timer):
    """A timer to get CPU time per thread.  Python 3.3 or later required."""

    def __init__(self):
        if sys.version_info < (3, 3):
            raise RuntimeError('Python 3.3 or later required.  '
                               'Use YappiTimer instead.')
        super(ThreadTimer, self).__init__()

    def __call__(self):
        return time.clock_gettime(time.CLOCK_THREAD_CPUTIME_ID)


class YappiTimer(Timer):
    """A timer to get CPU time per thread using `Yappi`_'s timer.

    .. _Yappi: https://code.google.com/p/yappi/

    """

    yappi = None

    def __init__(self):
        self.yappi = __import__('yappi')
        super(YappiTimer, self).__init__()

    def __call__(self):
        return self.yappi.get_clock_time()
