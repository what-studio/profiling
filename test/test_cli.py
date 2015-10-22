# -*- coding: utf-8 -*-
import click
from click.testing import CliRunner
import pytest

from profiling.__about__ import __version__
from profiling.__main__ import cli, Module, ProfilingCLI


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
