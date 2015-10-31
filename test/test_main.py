# -*- coding: utf-8 -*-
import io
from textwrap import dedent

import click

import profiling.__main__ as m
from profiling.sampling import SamplingProfiler
from profiling.sampling.samplers import TracingSampler
from profiling.tracing import TracingProfiler


def test_module_param_type():
    t = m.Module()
    # timeit
    filename, code, globals_ = t.convert('timeit', None, None)
    assert filename.endswith('timeit.py')
    assert code.co_filename.endswith('timeit.py')
    assert globals_['__name__'] == '__main__'
    assert globals_['__file__'].endswith('timeit.py')
    assert globals_['__package__'] == ''
    # profiling.__main__
    filename, code, globals_ = t.convert('profiling', None, None)
    assert filename.endswith('profiling/__main__.py')
    assert code.co_filename.endswith('profiling/__main__.py')
    assert globals_['__name__'] == '__main__'
    assert globals_['__file__'].endswith('profiling/__main__.py')
    assert globals_['__package__'] == 'profiling'


class MockFileIO(io.BytesIO):

    def close(self):
        self.seek(0)


def test_config(mocker):
    @click.command()
    @m.profiler_options
    def f(profiler_factory, **kwargs):
        profiler = profiler_factory()
        return profiler, kwargs
    # no config.
    mocker.patch('six.moves.builtins.open', side_effect=IOError)
    profiler, kwargs = f([], standalone_mode=False)
    assert isinstance(profiler, TracingProfiler)
    # config to use SamplingProfiler.
    mocker.patch('six.moves.builtins.open', return_value=MockFileIO(dedent('''
    [profiling]
    profiler = sampling
    sampler = tracing
    ''')))
    profiler, kwargs = f([], standalone_mode=False)
    assert isinstance(profiler, SamplingProfiler)
    assert isinstance(profiler.sampler, TracingSampler)
