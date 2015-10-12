# -*- coding: utf-8 -*-
import click
import pytest

import profiling.__main__ as m


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


def test_customized_cli():
    def f():
        pass
    cli = m.ProfilingCLI()
    cli.command(name='foo', aliases=['fooo', 'foooo'])(f)
    cli.implicit_command(name='bar')(f)
    with pytest.raises(RuntimeError):
        cli.implicit_command(name='baz')(f)
    assert len(cli.commands) == 2
    ctx = click.Context(cli)
    assert cli.get_command(ctx, 'foo').name == 'foo'
    assert cli.get_command(ctx, 'fooo').name == 'foo'
    assert cli.get_command(ctx, 'foooo').name == 'foo'
    assert cli.get_command(ctx, 'bar').name == 'bar'
    assert cli.get_command(ctx, 'hello.txt').name == 'bar'
