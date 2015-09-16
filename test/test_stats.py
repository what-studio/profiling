# -*- coding: utf-8 -*-
import pickle
from types import CodeType

from six import PY3

import profiling
from profiling.sortkeys import \
    by_name, by_own_hits, by_deep_time_per_call, by_own_time_per_call
from profiling.stats import FrozenStatistics, RecordingStatistics, Statistics


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
