# -*- coding: utf-8 -*-
try:
    import cPickle as pickle
except ImportError:
    import pickle
import sys
from textwrap import dedent
from types import CodeType

import pytest
from six import exec_, PY3

from _utils import spin
import profiling
from profiling.sortkeys import \
    by_deep_time_per_call, by_name, by_own_hits, by_own_time_per_call
from profiling.stats import \
    FlatFrozenStatistics, FrozenStatistics, RecordingStatistics, \
    spread_stats, Statistics
from profiling.tracing import TracingProfiler


def mock_code(name):
    """Makes a fake code object by name for built-in functions."""
    left_args = (0, 0, 0, 0, b'', (), (), (), '')
    if PY3:
        left_args = (0,) + left_args
    args = left_args + (name, 0, b'')
    return CodeType(*args)


def test_stats():
    stats = Statistics(name='foo', filename='bar', lineno=42)
    assert stats.regular_name == 'foo'
    stats.module = 'baz'
    assert stats.regular_name == 'baz:foo'
    assert stats.deep_time_per_call == 0
    assert stats.own_time_per_call == 0
    stats.deep_time = 128
    stats.own_hits = 4
    assert stats.deep_time_per_call == 32
    assert stats.own_time_per_call == 32
    assert len(stats) == 0
    assert not list(stats)


def test_repr():
    stats = Statistics(name='foo', own_hits=4, deep_time=128)
    assert repr(stats) == "<Statistics 'foo' hits=4 time=128.000000>"
    frozen = FrozenStatistics(name='foo', own_hits=4, deep_time=128,
                              children=[])
    frozen.children.append(Statistics(name='baz', own_hits=1, deep_time=120))
    assert \
        repr(frozen) == \
        "<FrozenStatistics 'foo' hits=4/5 time=8.000000/128.000000>"


def test_hash():
    stats1 = Statistics(name='foo', filename='bar', lineno=42)
    stats2 = Statistics(name='baz', filename='bar', lineno=89)
    stats_dics = {stats1: 1, stats2: 2}
    assert stats_dics[stats1] == 1
    assert stats_dics[stats2] == 2


def test_recording():
    # profiling is a module not code.
    # but inspect.getmodule() works like with code of a module.
    assert RecordingStatistics(profiling).module == 'profiling'
    # use discard_child.
    stats = RecordingStatistics()
    assert None not in stats
    stats.ensure_child(None)
    assert None in stats
    stats.discard_child(None)
    assert None not in stats
    stats.discard_child(None)
    assert None not in stats


# def test_recording():
#     stats.wall = lambda: 10
#     stats.record_starting(0)
#     code = mock_code('foo')
#     stats = RecordingStatistics(code)
#     assert stats.name == 'foo'
#     assert stats.own_hits == 0
#     assert stats.deep_time == 0
#     stats.record_entering(100)
#     stats.record_leaving(200)
#     assert stats.own_hits == 1
#     assert stats.deep_time == 100
#     stats.record_entering(200)
#     stats.record_leaving(400)
#     assert stats.own_hits == 2
#     assert stats.deep_time == 300
#     code2 = mock_code('bar')
#     stats2 = RecordingStatistics(code2)
#     assert code2 not in stats
#     stats.add_child(code2, stats2)
#     assert code2 in stats
#     assert stats.get_child(code2) is stats2
#     assert len(stats) == 1
#     assert list(stats) == [stats2]
#     assert stats.deep_time == 300
#     assert stats.own_time == 300
#     stats2.record_entering(1000)
#     stats2.record_leaving(1004)
#     assert stats2.deep_time == 4
#     assert stats2.own_time == 4
#     assert stats.deep_time == 300
#     assert stats.own_time == 296
#     stats.clear()
#     assert len(stats) == 0
#     with pytest.raises(TypeError):
#         pickle.dumps(stats)
#     stats3 = stats.ensure_child(mock_code('baz'), VoidRecordingStatistics)
#     assert isinstance(stats3, VoidRecordingStatistics)
#     stats.wall = lambda: 2000
#     stats.record_stopping(400)
#     assert stats.cpu_time == 400
#     assert stats.wall_time == 1990
#     assert stats.cpu_usage == 400 / 1990.


def test_pickle():
    stats = Statistics(name='ok')
    for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
        assert pickle.loads(pickle.dumps(stats, protocol)).name == 'ok'


def test_frozen():
    code = mock_code('foo')
    stats = RecordingStatistics(code)
    stats.deep_time = 10
    stats.ensure_child(None)
    # RecordingStatistics are frozen at pickling.
    frozen_stats = pickle.loads(pickle.dumps(stats))
    assert frozen_stats.name == 'foo'
    assert frozen_stats.deep_time == 10
    assert len(frozen_stats) == 1
    restored_frozen_stats = pickle.loads(pickle.dumps(frozen_stats))
    assert restored_frozen_stats.name == 'foo'
    assert restored_frozen_stats.deep_time == 10
    assert len(restored_frozen_stats) == 1


def test_flatten():
    stats = FrozenStatistics(children=[
        FrozenStatistics('foo', own_hits=10, children=[
            FrozenStatistics('foo', own_hits=20, children=[]),
            FrozenStatistics('bar', own_hits=30, children=[]),
        ]),
        FrozenStatistics('bar', own_hits=40, children=[]),
        FrozenStatistics('baz', own_hits=50, children=[]),
    ])
    flat_stats = FlatFrozenStatistics.flatten(stats)
    children = {stats.name: stats for stats in flat_stats}
    assert len(children) == 3
    assert children['foo'].own_hits == 30
    assert children['bar'].own_hits == 70
    assert children['baz'].own_hits == 50


def test_spread_stats():
    stats = FrozenStatistics(children=[
        FrozenStatistics('foo', own_hits=10, children=[
            FrozenStatistics('foo', own_hits=20, children=[]),
            FrozenStatistics('bar', own_hits=30, children=[]),
        ]),
        FrozenStatistics('bar', own_hits=40, children=[]),
        FrozenStatistics('baz', own_hits=50, children=[]),
    ])
    descendants = list(spread_stats(stats))
    assert len(descendants) == 5
    assert descendants[0].name == 'foo'
    assert descendants[1].name == 'bar'
    assert descendants[2].name == 'baz'
    assert descendants[3].name == 'foo'
    assert descendants[4].name == 'bar'


def test_sorting():
    stats = RecordingStatistics(mock_code('foo'))
    stats1 = RecordingStatistics(mock_code('bar'))
    stats2 = RecordingStatistics(mock_code('baz'))
    stats3 = RecordingStatistics(mock_code('qux'))
    stats.add_child(stats1.code, stats1)
    stats.add_child(stats2.code, stats2)
    stats.add_child(stats3.code, stats3)
    stats.deep_time = 100
    stats1.deep_time = 20
    stats1.own_hits = 3
    stats2.deep_time = 30
    stats2.own_hits = 2
    stats3.deep_time = 40
    stats3.own_hits = 4
    assert stats.sorted() == [stats3, stats2, stats1]
    assert stats.sorted(by_own_hits) == [stats3, stats1, stats2]
    assert stats.sorted(~by_own_hits) == [stats2, stats1, stats3]
    assert stats.sorted(by_deep_time_per_call) == [stats2, stats3, stats1]
    assert stats.sorted(by_own_time_per_call) == [stats2, stats3, stats1]
    assert stats.sorted(by_name) == [stats1, stats2, stats3]


@pytest.fixture
def deep_stats(depth=sys.getrecursionlimit(), skip_if_no_recursion_error=True):
    # Define a function with deep recursion.
    def x0(frames):
        frames.append(sys._getframe())
    locals_ = locals()
    for x in range(1, depth):
        code = dedent('''
        import sys
        def x%d(frames):
            frames.append(sys._getframe())
            x%d(frames)
        ''' % (x, x - 1))
        exec_(code, locals_)
    f = locals_['x%d' % (depth - 1)]
    frames = []
    try:
        f(frames)
    except RuntimeError:
        # Expected.
        pass
    else:
        # Maybe PyPy.
        if skip_if_no_recursion_error:
            pytest.skip('Recursion limit not exceeded')
    # Profile the deepest frame.
    profiler = TracingProfiler()
    profiler._profile(frames[-1], 'call', None)
    spin(0.5)
    profiler._profile(frames[-1], 'return', None)
    # Test with the result.
    stats, __, __ = profiler.result()
    return stats


def test_recursion_limit(deep_stats):
    deepest_stats = list(spread_stats(deep_stats))[-1]
    assert deepest_stats.deep_time > 0
    # It exceeded the recursion limit until 6fe1b48.
    assert deep_stats.children[0].deep_time == deepest_stats.deep_time
    # Pickling.
    assert isinstance(deep_stats, RecordingStatistics)
    data = pickle.dumps(deep_stats)
    frozen_stats = pickle.loads(data)
    assert isinstance(frozen_stats, FrozenStatistics)
    deepest_frozen_stats = list(spread_stats(frozen_stats))[-1]
    assert deepest_stats.deep_time == deepest_frozen_stats.deep_time


def test_deep_stats_dump_performance(benchmark):
    stats = deep_stats(100, skip_if_no_recursion_error=False)
    benchmark(lambda: pickle.dumps(stats))


def test_deep_stats_load_performance(benchmark):
    stats = deep_stats(100, skip_if_no_recursion_error=False)
    data = pickle.dumps(stats)
    benchmark(lambda: pickle.loads(data))


def test_shallow_stats_dump_performance(benchmark):
    stats = deep_stats(5, skip_if_no_recursion_error=False)
    benchmark(lambda: pickle.dumps(stats))


def test_shallow_stats_load_performance(benchmark):
    stats = deep_stats(5, skip_if_no_recursion_error=False)
    data = pickle.dumps(stats)
    benchmark(lambda: pickle.loads(data))
