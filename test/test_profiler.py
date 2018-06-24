# -*- coding: utf-8 -*-
try:
    import cPickle as pickle
except ImportError:
    import pickle
from os import path
import tempfile

import pytest

from _utils import foo, spin
from profiling.profiler import Profiler, ProfilerWrapper


class NullProfiler(Profiler):

    def run(self):
        yield


class NullProfilerWrapper(ProfilerWrapper):

    def run(self):
        with self.profiler:
            yield


@pytest.fixture
def profiler():
    return NullProfiler()


def test_exclude_code(profiler):
    foo_code = foo().f_code
    with profiler:
        assert foo_code not in profiler.stats
        profiler.stats.ensure_child(foo_code)
        assert foo_code in profiler.stats
        profiler.exclude_code(foo_code)
        assert foo_code not in profiler.stats
        profiler.exclude_code(foo_code)
        assert foo_code not in profiler.stats


def test_result(profiler):
    __, cpu_time, wall_time = profiler.result()
    assert cpu_time == wall_time == 0.0
    with profiler:
        spin(0.1)
    __, cpu_time, wall_time = profiler.result()
    assert cpu_time > 0.0
    assert wall_time >= 0.1


def test_dump(profiler):
    temp_dir = tempfile.mkdtemp()
    temp_file = path.join(temp_dir, "file.prf")

    profiler.dump(temp_file)

    assert path.getsize(temp_file) > 0

    with open(temp_file, 'rb') as f:
        profiler_class, (stats, cpu_time, wall_time) = pickle.load(f)

    assert profiler.__class__ == profiler_class
    assert cpu_time == wall_time == 0.0


def test_wrapper(profiler):
    wrapper = NullProfilerWrapper(profiler)
    assert isinstance(wrapper, Profiler)
    assert wrapper.table_class is profiler.table_class
    assert wrapper.stats is profiler.stats
    __, cpu_time, wall_time = wrapper.result()
    assert cpu_time == wall_time == 0.0
    with wrapper:
        assert wrapper.is_running()
        assert profiler.is_running()
    assert not wrapper.is_running()
    assert not profiler.is_running()
