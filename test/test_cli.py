# -*- coding: utf-8 -*-
from click.testing import CliRunner

from profiling.__main__ import cli


cli_runner = CliRunner()


def test_profiling_command_usage():
    for cmd in ['profile', 'live-profile', 'remote-profile']:
        r = cli_runner.invoke(cli, [cmd, '--help'])
        assert 'SCRIPT [--] [ARGV]...' in r.output
