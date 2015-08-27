# -*- coding: utf-8 -*-
"""
    profiling.utils
    ~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
from collections import deque
from contextlib import contextmanager

try:
    from . import speedup
except ImportError:
    speedup = False


__all__ = ['Runnable', 'frame_stack', 'repr_frame', 'lazy_import', 'deferral']


class Runnable(object):
    """The base class for runnable classes such as :class:`profiling.profiler.
    Profiler`.
    """

    #: The generator :meth:`run` returns.  It will be set by :meth:`start`.
    _running = None

    def is_running(self):
        """Whether the instance is running."""
        return self._running is not None

    def start(self, *args, **kwargs):
        """Starts the instance.

        :raises RuntimeError: has been already started.
        :raises TypeError: :meth:`run` is not canonical.

        """
        if self.is_running():
            raise RuntimeError('Already started')
        self._running = self.run(*args, **kwargs)
        try:
            yielded = next(self._running)
        except StopIteration:
            raise TypeError('run() must yield just one time')
        if yielded is not None:
            raise TypeError('run() must yield without value')

    def stop(self):
        """Stops the instance.

        :raises RuntimeError: has not been started.
        :raises TypeError: :meth:`run` is not canonical.

        """
        if not self.is_running():
            raise RuntimeError('Not started')
        running, self._running = self._running, None
        try:
            next(running)
        except StopIteration:
            # expected.
            pass
        else:
            raise TypeError('run() must yield just one time')

    def run(self, *args, **kwargs):
        """Override it to implement the starting and stopping behavior.

        An overriding method must be a generator function which yields just one
        time without any value.  :meth:`start` creates and iterates once the
        generator it returns.  Then :meth:`stop` will iterates again.

        :raises NotImplementedError: :meth:`run` is not overridden.

        """
        raise NotImplementedError('Implement run()')
        yield

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc_info):
        self.stop()


if speedup:
    def frame_stack(frame, top_frame=None, top_code=None):
        """Returns a deque of frame stack."""
        return speedup.frame_stack(frame, top_frame, top_code)
else:
    def frame_stack(frame, top_frame=None, top_code=None):
        """Returns a deque of frame stack."""
        frames = deque()
        while frame is not None:
            frames.appendleft(frame)
            if frame is top_frame or frame.f_code is top_code:
                break
            frame = frame.f_back
        return frames


def repr_frame(frame):
    return '%s:%d' % (frame.f_code.co_filename, frame.f_lineno)


class LazyImport(object):

    def __init__(self, module_name):
        self.module_name = module_name
        self.module = None

    def __get__(self, obj, cls):
        if self.module is None:
            self.module = __import__(self.module_name)
        return self.module


lazy_import = LazyImport


@contextmanager
def deferral():
    """Defers a function call when it is being required like Go.

    ::

       with deferral() as defer:
           sys.setprofile(f)
           defer(sys.setprofile, None)
           # do something.

    """
    deferred = []
    defer = lambda f, *a, **k: deferred.append((f, a, k))
    try:
        yield defer
    finally:
        while deferred:
            f, a, k = deferred.pop()
            f(*a, **k)
