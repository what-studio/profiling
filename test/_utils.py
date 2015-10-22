# -*- coding: utf-8 -*-
from textwrap import dedent
import time


__all__ = ['find_multiple_stats', 'find_stats', 'factorial', 'spin',
           'mock_code_names']


def find_multiple_stats(stats, name, _found=None, _on_found=None):
    if _found is None:
        _found = []
    for child_stats in stats:
        if child_stats.name == name:
            _found.append(child_stats)
            if callable(_on_found):
                _on_found(_found)
        find_multiple_stats(child_stats, name, _found)
    return _found


def find_stats(stats, name):
    def _on_found(found):
        raise StopIteration
    return find_multiple_stats(stats, name)[0]


def factorial(n):
    f = 1
    while n:
        f *= n
        n -= 1
    return f


def spin(seconds):
    t = time.time()
    x = 0
    while time.time() - t < seconds:
        x += 1
    return x


foo = None  # placeheolder
mock_code_names = ['foo', 'bar', 'baz']
source = ''
for name, next_name in zip(mock_code_names[:-1], mock_code_names[1:]):
    source += dedent('''
    def {0}():
        return {1}()
    ''').format(name, next_name)
source += '''
def {0}():
    return __import__('sys')._getframe()
'''.format(mock_code_names[-1])
exec(source)
__all__.extend(mock_code_names)
