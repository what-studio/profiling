# -*- coding: utf-8 -*-
from contextlib import contextmanager


__all__ = ['profiling', 'find_stats', 'find_stat', 'factorial']


@contextmanager
def profiling(profiler):
    try:
        profiler.start()
        yield
    finally:
        if profiler.is_running():
            profiler.stop()


def find_stats(stats, name, _found=None, _on_found=None):
    if _found is None:
        _found = []
    for stat in stats:
        if stat.name == name:
            _found.append(stat)
            if callable(_on_found):
                _on_found(_found)
        find_stats(stat, name, _found)
    return _found


def find_stat(stats, name):
    def _on_found(found):
        raise StopIteration
    return find_stats(stats, name)[0]


def factorial(n):
    f = 1
    while n:
        f *= n
        n -= 1
    return f
