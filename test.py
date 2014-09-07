# -*- coding: utf-8 -*-
from profiling.profiler import make_code
from profiling.stats import Stat, RecordingStat


def test_stat():
    stat = Stat(name='foo', filename='bar', lineno=42)
    assert stat.regular_name == 'foo'
    stat.module = 'baz'
    assert stat.regular_name == 'baz:foo'
    assert stat.total_time_per_call == 0
    stat.total_time = 128
    stat.calls = 4
    assert stat.total_time_per_call == 32
    assert not list(stat)
    assert len(stat) == 0


def test_recording():
    code = make_code('foo')
    stat = RecordingStat(code)
    assert stat.name == 'foo'
    assert stat.calls == 0
    assert stat.total_time == 0
    stat.record_entering(100)
    stat.record_leaving(200)
    assert stat.calls == 1
    assert stat.total_time == 100
    stat.record_entering(200)
    stat.record_leaving(400)
    assert stat.calls == 2
    assert stat.total_time == 300
    code2 = make_code('bar')
    stat2 = RecordingStat(code2)
    stat.add_child(code2, stat2)
    assert stat.total_time == 300
    assert stat.own_time == 300
    stat2.record_entering(1000)
    stat2.record_leaving(1004)
    assert stat2.total_time == 4
    assert stat2.own_time == 4
    assert stat.total_time == 300
    assert stat.own_time == 296
