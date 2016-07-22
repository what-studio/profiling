# -*- coding: utf-8 -*-
import io
import textwrap

import click
from click.testing import CliRunner
from six.moves import builtins
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
    cli = ProfilingCLI(default='bar')
    @cli.command(aliases=['fooo', 'foooo'])
    def foo():
        pass
    @cli.command()
    @click.argument('l', default='answer')
    @click.option('-n', type=int, default=0)
    def bar(l, n=0):
        click.echo('%s: %d' % (l, n))
    assert len(cli.commands) == 2
    ctx = click.Context(cli)
    assert cli.get_command(ctx, 'foo').name == 'foo'
    assert cli.get_command(ctx, 'fooo').name == 'foo'
    assert cli.get_command(ctx, 'foooo').name == 'foo'
    assert cli.get_command(ctx, 'bar').name == 'bar'
    assert cli.get_command(ctx, 'hello.txt').name == 'bar'
    assert 'Usage:' in cli_runner.invoke(cli, []).output
    assert cli_runner.invoke(cli, ['zero']).output == 'zero: 0\n'
    assert cli_runner.invoke(cli, ['one', '-n', '1']).output == 'one: 1\n'
    assert cli_runner.invoke(cli, ['-n', '42']).output == 'answer: 42\n'
    assert 'no such option' in cli_runner.invoke(cli, ['-x']).output


def test_profiling_command_usage():
    for cmd in ['profile', 'live-profile', 'remote-profile']:
        r = cli_runner.invoke(cli, [cmd, '--help'])
        assert 'SCRIPT [--] [ARGV]...' in r.output


def test_version():
    r = cli_runner.invoke(cli, ['--version'])
    assert r.output.strip() == 'profiling, version %s' % __version__


def test_config(monkeypatch):
    @click.command()
    @profiler_options
    def f(profiler_factory, **kwargs):
        profiler = profiler_factory()
        return profiler, kwargs
    # no config.
    def io_error(*args, **kwargs):
        raise IOError
    monkeypatch.setattr(builtins, 'open', io_error)
    profiler, kwargs = f([], standalone_mode=False)
    assert isinstance(profiler, TracingProfiler)
    # config to use SamplingProfiler.
    monkeypatch.setattr(builtins, 'open', lambda *a, **k: mock_file(u'''
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
    monkeypatch.setattr(builtins, 'open', mock_open)
    profiler, kwargs = f([], standalone_mode=False)
    assert isinstance(profiler, SamplingProfiler)  # from setup.cfg
    assert kwargs['pickle_protocol'] == 0  # from .profiling
