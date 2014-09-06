# -*- coding: utf-8 -*-
"""
    profiling.__main__
    ~~~~~~~~~~~~~~~~~~

    The command-line interface.

    .. sourcecode:: console

       $ python -m profiling --help

"""
from __future__ import absolute_import
from datetime import datetime
import importlib
import os
try:
    import cPickle as pickle
except ImportError:
    import pickle
import socket
from stat import S_ISREG, S_ISSOCK
import sys

import click
from six import PY2, exec_
import urwid

from .profiler import Profiler
from .remote import recv_stats
from .viewer import StatisticsViewer


__all__ = ['main', 'profile', 'view']


@click.group()
def main():
    pass


def make_viewer():
    viewer = StatisticsViewer()
    viewer.use_vim_command_map()
    viewer.use_game_command_map()
    return viewer


timers = {
    # timer name: (timer module name, timer class name)
    None: ('.timers', 'Timer'),
    'thread': ('.timers.thread', 'ThreadTimer'),
    'yappi': ('.timers.thread', 'YappiTimer'),
    'greenlet': ('.timers.greenlet', 'GreenletTimer'),
}


def get_timer(ctx, param, value):
    try:
        module_name, class_name = timers[value]
    except KeyError:
        raise ValueError('No such timer: {0}'.format(value))
    module = importlib.import_module(module_name, __package__)
    timer_class = getattr(module, class_name)
    return timer_class()


@main.command()
@click.argument('script', type=click.File('rb'))
@click.option('-t', '--timer', callback=get_timer)
@click.option('-d', '--dump', 'dump_filename', type=click.Path(writable=True))
@click.option('--mono', is_flag=True)
def profile(script, timer=None, dump_filename=None, mono=False):
    """Profile a Python script."""
    code = compile(script.read(), script.name, 'exec')
    script.close()
    sys.argv[:] = [script.name]
    globals_ = {
        '__file__': script.name,
        '__name__': '__main__',
        '__package__': None,
    }
    profiler = Profiler(timer)
    frame = sys._getframe()
    profiler.start(top_frame=frame, top_code=code)
    try:
        exec_(code, globals_)
    finally:
        profiler.stop()
    if PY2:
        # in Python 2, exec's cpu time is duplicated with actual cpu time.
        stat = profiler.stats.get_child(frame.f_code)
        stat.remove_child(exec_.func_code)
    if dump_filename is None:
        viewer = make_viewer()
        viewer.set_stats(profiler.stats)
        loop = viewer.loop()
        if mono:
            loop.screen.set_terminal_properties(1)
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
    """Parses a source string to source type and source name.

    :returns: a tuple containing source type and source name.

    """
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
        raise ValueError('A dump file or a socket addr required.')
    return src_type, src


class start_client:
    """Starts a client of profiler server which is running by :func:`profiling.
    remote.run_server` behind the `Urwid`_ event loop. Just call this like a
    function.

    .. _Urwid: http://urwid.org/

    """

    def __init__(self, viewer, event_loop, addr, sock_family=socket.AF_INET,
                 sock_type=socket.SOCK_STREAM, timeout=10):
        self.viewer = viewer
        self.event_loop = event_loop
        self.addr = addr
        self.sockopts = (sock_family, sock_type)
        self.timeout = timeout
        self.create_connection()

    def create_connection(self, delay=0):
        self.sock = socket.socket(*self.sockopts)
        self.sock.setblocking(0)
        self.event_loop.alarm(delay, self.connect)

    def connect(self):
        errno = self.sock.connect_ex(self.addr)
        assert errno == 115
        self.event_loop.watch_file(self.sock.fileno(), self.received)

    def disconnect(self):
        self.event_loop.remove_watch_file(self.sock.fileno())
        self.sock.close()

    def received(self):
        self.event_loop.remove_alarm(getattr(self, '_t', None))
        self.viewer.activate()
        try:
            stats = recv_stats(self.sock)
        except socket.error as exc:
            # try to reconnect.
            self.viewer.inactivate()
            self.disconnect()
            self.create_connection(1 if exc.errno == 111 else 0)
            return
        src_time = datetime.now()
        self.viewer.set_stats(stats, self.addr, src_time)
        self._t = self.event_loop.alarm(self.timeout, self.viewer.inactivate)


@main.command()
@click.argument('src', metavar='SOURCE')
@click.option('--timeout', type=float, default=10)
@click.option('--mono', is_flag=True)
def view(src, timeout=10, mono=False):
    """Inspect statistics by TUI view."""
    try:
        src_type, src = parse_src(src)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint='src')
    viewer = make_viewer()
    event_loop = urwid.SelectEventLoop()
    if src_type == 'dump':
        with open(src) as f:
            stats = pickle.load(f)
        src_time = datetime.fromtimestamp(os.path.getmtime(src))
        viewer.set_stats(stats, src, src_time)
    elif src_type in ('tcp', 'sock'):
        family = {'tcp': socket.AF_INET, 'sock': socket.AF_UNIX}[src_type]
        start_client(viewer, event_loop, src, family, timeout=timeout)
    loop = viewer.loop(event_loop=event_loop)
    if mono:
        loop.screen.set_terminal_properties(1)
    try:
        loop.run()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
