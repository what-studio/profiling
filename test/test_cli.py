# -*- coding: utf-8 -*-
import io
import textwrap

import click
from click.testing import CliRunner
import pytest
from valuedispatch import valuedispatch

from profiling.__about__ import __version__
from profiling.__main__ import cli, Module, profiler_options, ProfilingCLI
from profiling.sampling import SamplingProfiler
from profiling.sampling.samplers import TracingSampler
from profiling.tracing import TracingProfiler


class MockFileIO(io.StringIO):

    def close(self):
        self.seek(0)


def mock_file(indented_content):
    return MockFileIO(textwrap.dedent(indented_content))


cli_runner = CliRunner()


def test_module_param_type():
    t = Module()
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


def test_customized_cli():
    def f():
        pass
    cli = ProfilingCLI()
    cli.command(name='foo', aliases=['fooo', 'foooo'])(f)
    cli.command(name='bar', implicit=True)(f)
    with pytest.raises(RuntimeError):
        cli.command(name='baz', implicit=True)(f)
    assert len(cli.commands) == 2
    ctx = click.Context(cli)
    assert cli.get_command(ctx, 'foo').name == 'foo'
    assert cli.get_command(ctx, 'fooo').name == 'foo'
    assert cli.get_command(ctx, 'foooo').name == 'foo'
    assert cli.get_command(ctx, 'bar').name == 'bar'
    assert cli.get_command(ctx, 'hello.txt').name == 'bar'


def test_profiling_command_usage():
    for cmd in ['profile', 'live-profile', 'remote-profile']:
        r = cli_runner.invoke(cli, [cmd, '--help'])
        assert 'SCRIPT [--] [ARGV]...' in r.output


def test_version():
    r = cli_runner.invoke(cli, ['--version'])
    assert r.output.strip() == 'profiling, version %s' % __version__


def test_config(mocker):
    @click.command()
    @profiler_options
    def f(profiler_factory, **kwargs):
        profiler = profiler_factory()
        return profiler, kwargs
    # no config.
    mocker.patch('six.moves.builtins.open', side_effect=IOError)
    profiler, kwargs = f([], standalone_mode=False)
    assert isinstance(profiler, TracingProfiler)
    # config to use SamplingProfiler.
    mocker.patch('six.moves.builtins.open', return_value=mock_file(u'''
    [profiling]
    profiler = sampling
    sampler = tracing
    '''))
    profiler, kwargs = f([], standalone_mode=False)
    assert isinstance(profiler, SamplingProfiler)
    assert isinstance(profiler.sampler, TracingSampler)
    # set both of setup.cfg and .profiling.
    @valuedispatch
    def mock_open(path, *args, **kwargs):
        raise IOError
    @mock_open.register('setup.cfg')
    def open_setup_cfg(*_, **__):
        return mock_file(u'''
        [profiling]
        profiler = sampling
        pickle-protocol = 3
        ''')
    @mock_open.register('.profiling')
    def open_profiling(*_, **__):
        return mock_file(u'''
        [profiling]
        pickle-protocol = 0
        ''')
    mocker.patch('six.moves.builtins.open', side_effect=mock_open)
    profiler, kwargs = f([], standalone_mode=False)
    assert isinstance(profiler, SamplingProfiler)  # from setup.cfg
    assert kwargs['pickle_protocol'] == 0  # from .profiling
