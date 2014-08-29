# -*- coding: utf-8 -*-
"""
    profiling.__main__
    ~~~~~~~~~~~~~~~~~~

    The command-line interface.

"""
from __future__ import absolute_import
from datetime import datetime
import os
try:
    import cPickle as pickle
except ImportError:
    import pickle
from stat import S_ISREG, S_ISSOCK
import sys

import click
import gevent
from gevent import socket
from urwid_geventloop import GeventLoop

from .profiler import Profiler
from .remote import recv_stats
from .timers import Timer
from .timers.greenlet import GreenletTimer
from .viewer import StatisticsViewer


def make_viewer():
    viewer = StatisticsViewer()
    viewer.use_vim_command_map()
    return viewer


def get_timer(ctx, param, value):
    if not value:
        return Timer()
    elif value == 'greenlet':
        return GreenletTimer()
    else:
        raise ValueError('No such timer: {0}'.format(value))


@click.group()
def main():
    pass


@main.command()
@click.argument('script', type=click.File('rb'))
@click.option('-t', '--timer', callback=get_timer)
@click.option('-d', '--dump', 'dump_filename', type=click.Path(writable=True))
def profile(script, timer=None, dump_filename=None):
    code = compile(script.read(), script.name, 'exec')
    script.close()
    sys.argv[:] = [script.name]
    globals_ = {
        '__file__': script.name,
        '__name__': '__main__',
        '__package__': None,
    }
    profiler = Profiler(timer)
    profiler.start()
    try:
        exec code in globals_
    finally:
        profiler.stop()
    if dump_filename is None:
        viewer = make_viewer()
        viewer.set_stats(profiler.stats)
        loop = viewer.loop()
        try:
            loop.run()
        except KeyboardInterrupt:
            pass
    else:
        stats = profiler.frozen_stats()
        with open(dump_filename, 'w') as f:
            pickle.dump(stats, f)
        click.echo('To view statistics:')
        click.echo('  $ python -m profiling view ', nl=False)
        click.secho(dump_filename, underline=True)


def parse_src(src):
    src_type = False
    try:
        mode = os.stat(src).st_mode
    except OSError:
        try:
            host, port = src.split(':')
        except ValueError:
            pass
        else:
            src_type = 'tcp'
            port = int(port)
            src = (host, port)
    else:
        if S_ISSOCK(mode):
            src_type = 'sock'
        elif S_ISREG(mode):
            src_type = 'dump'
    if not src_type:
        raise ValueError('A dump file or a socket address required.')
    return src_type, src


def run_client(viewer, address, *socket_options):
    while True:
        sock = socket.socket(*socket_options)
        try:
            sock.connect(address)
        except socket.error:
            viewer.inactivate()
            gevent.sleep(1)
            # try to reconnect
            continue
        while not sock.closed:
            try:
                with gevent.Timeout(60):
                    stats = recv_stats(sock)
            except (gevent.Timeout, socket.error):
                sock.close()
                # try to reconnect quickly
                break
            src_time = datetime.now()
            viewer.set_stats(stats, address, src_time)


@main.command()
@click.argument('src', metavar='SOURCE')
def view(src):
    try:
        src_type, src = parse_src(src)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint='src')
    viewer = make_viewer()
    if src_type == 'tcp':
        gevent.spawn(run_client, viewer, src)
        event_loop = GeventLoop()
    elif src_type == 'sock':
        gevent.spawn(run_client, viewer, src, socket.AF_UNIX)
        event_loop = GeventLoop()
    elif src_type == 'dump':
        with open(src) as f:
            stats = pickle.load(f)
        src_time = datetime.fromtimestamp(os.path.getmtime(src))
        viewer.set_stats(stats, src, src_time)
        event_loop = None
    loop = viewer.loop(event_loop=event_loop)
    try:
        loop.run()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
