# -*- coding: utf-8 -*-
"""
    profiling.profiler
    ~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import

from .stats import FrozenStatistics, RecordingStatistics
from .viewer import StatisticsTable


__all__ = ['Profiler']


class Profiler(object):
    """The base class for profiler."""

    #: A widget class which extends :class:`profiling.viewer.StatisticsTable`.
    table_class = StatisticsTable

    #: The root recording statistics.
    stats = None

    top_frame = None
    top_code = None

    #: The generator :meth:`run` returns.  It will be set by :meth:`start`.
    _running = None

    def __init__(self, top_frame=None, top_code=None):
        self.top_frame = top_frame
        self.top_code = top_code
        self.clear()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc_info):
        self.stop()

    def exclude_code(self, code):
        """Excludes statistics of the given code."""
        try:
            self.stats.remove_child(code)
        except KeyError:
            pass

    def result(self):
        """Gets the frozen statistics to serialize by Pickle."""
        return FrozenStatistics(self.stats)

    def clear(self):
        """Clears or initializes the recording statistics."""
        if self.stats is None:
            self.stats = RecordingStatistics()
        else:
            self.stats.clear()

    def is_running(self):
        """Whether the profiler is running."""
        return self._running is not None

    def start(self):
        """Starts the profiler.

        :raises RuntimeError: the profiler has been already started.
        :raises TypeError: :meth:`run` is not canonical.

        """
        if self.is_running():
            raise RuntimeError('Already started')
        self._running = self.run()
        try:
            yielded = next(self._running)
        except StopIteration:
            raise TypeError('run() must yield just one time')
        if yielded is not None:
            raise TypeError('run() must yield without value')

    def stop(self):
        """Stops the profiler.

        :raises RuntimeError: the profiler has not been started.
        :raises TypeError: :meth:`run` is not canonical.

        """
        if not self.is_running():
            raise RuntimeError('Not started')
        try:
            next(self._running)
        except StopIteration:
            # expected.
            pass
        else:
            raise TypeError('run() must yield just one time')
        finally:
            self._running = None

    def run(self):
        """Override it to implement the starting and stopping behavior.

        An overriding method must be a generator function which yields just one
        time without any value.  :meth:`start` creates and iterates once the
        generator it returns.  Then :meth:`stop` will iterates again.

        :raises NotImplementedError: :meth:`run` is not overridden.

        """
        raise NotImplementedError('Implement run()')
        yield


class ProfilerWrapper(Profiler):

    for attr in ['table_class', 'stats', 'top_frame', 'top_code',
                 'result', 'clear', 'is_running']:
        f = lambda self, attr=attr: getattr(self.profiler, attr)
        locals()[attr] = property(f)
        del f

    def __init__(self, profiler):
        self.profiler = profiler
