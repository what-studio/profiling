# -*- coding: utf-8 -*-
"""
    profiling.__main__
    ~~~~~~~~~~~~~~~~~~

    The command-line interface to profile a script or view profiling results.

    .. sourcecode:: console

       $ python -m profiling --help

"""
from __future__ import absolute_import
from collections import OrderedDict
from datetime import datetime
import importlib
import os
try:
    import cPickle as pickle
except ImportError:
    import pickle
import signal
import socket
from stat import S_ISREG, S_ISSOCK
import sys
import threading
import traceback

import click
from six import PY2, exec_

from .profiler import Profiler
from .remote import INTERVAL, PICKLE_PROTOCOL, recv_stats
from .remote.background import BackgroundProfiler
from .remote.select import SelectProfilingServer
from .viewer import StatisticsViewer


__all__ = ['main', 'profile', 'view']


@click.group()
def main():
    pass


def make_viewer(mono=False):
    viewer = StatisticsViewer()
    viewer.use_vim_command_map()
    viewer.use_game_command_map()
    loop = viewer.loop()
    if mono:
        loop.screen.set_terminal_properties(1)
    return (viewer, loop)


def spawn_thread(func, *args, **kwargs):
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()
    return thread


noop = lambda x: x


# custom parameter types


class Script(click.File):

    def __init__(self):
        super(Script, self).__init__('rb')

    def convert(self, value, param, ctx):
        with super(Script, self).convert(value, param, ctx) as f:
            filename = f.name
            code = compile(f.read(), filename, 'exec')
            globals_ = {'__file__': filename,
                        '__name__': '__main__',
                        '__package__': None}
        return (filename, code, globals_)

    def get_metavar(self, param):
        return 'PYTHON'


class Timer(click.ParamType):

    timers = OrderedDict([
        # timer name: (timer module name, timer class name)
        (None, ('.timers', 'Timer')),
        ('thread', ('.timers.thread', 'ThreadTimer')),
        ('yappi', ('.timers.thread', 'YappiTimer')),
        ('greenlet', ('.timers.greenlet', 'GreenletTimer')),
    ])

    def import_timer_class(self, name):
        try:
            module_name, class_name = self.timers[name]
        except KeyError:
            raise ValueError('No such timer: {0}'.format(name))
        module = importlib.import_module(module_name, __package__)
        timer_class = getattr(module, class_name)
        return timer_class

    def convert(self, value, param, ctx):
        if value == 'default':
            value = None
        timer_class = self.import_timer_class(value)
        return timer_class()

    def get_metavar(self, param):
        return 'TIMER'


class Address(click.ParamType):

    def convert(self, value, param, ctx):
        host, port = value.split(':')
        port = int(port)
        return (host, port)

    def get_metavar(self, param):
        return 'HOST:PORT'


class ViewSource(click.ParamType):

    def convert(self, value, param, ctx):
        src_type = False
        try:
            mode = os.stat(value).st_mode
        except OSError:
            try:
                src_name = Address().convert(value, param, ctx)
            except ValueError:
                pass
            else:
                src_type = 'tcp'
        else:
            src_name = value
            if S_ISSOCK(mode):
                src_type = 'sock'
            elif S_ISREG(mode):
                src_type = 'dump'
        if not src_type:
            raise ValueError('A dump file or a socket addr required.')
        return (src_type, src_name)

    def get_metavar(self, param):
        return 'SOURCE'


class SignalNumber(click.IntRange):

    def __init__(self):
        super(SignalNumber, self).__init__(0, 255)

    def get_metavar(self, param):
        return 'SIGNO'


# common parameters


class Params(object):

    def __init__(self, params):
        super(Params, self).__init__()
        self.params = params

    def __call__(self, f):
        for param in self.params:
            f = param(f)
        return f

    def extend(self, params):
        return type(self)(self.params + params)


profiler_params = Params([
    click.argument('script', type=Script()),
    click.option('-t', '--timer', type=Timer(),
                 help='Choose CPU time measurer.'),
    click.option('--pickle-protocol', type=int, default=PICKLE_PROTOCOL),
])
live_profiler_params = profiler_params.extend([
    click.option('-i', '--interval', type=float, default=INTERVAL,
                 help='How often update the profiling result.'),
])
viewer_params = Params([
    click.option('--mono', is_flag=True, help='Disable coloring.'),
])


# sub-commands


@main.command()
@profiler_params
@click.option('-d', '--dump', 'dump_filename', type=click.Path(writable=True))
@viewer_params
def profile(script, timer, pickle_protocol, dump_filename, mono):
    """Profile a Python script."""
    filename, code, globals_ = script
    sys.argv[:] = [filename]
    # start profiling.
    frame = sys._getframe()
    profiler = Profiler(timer, top_frame=frame, top_code=code)
    profiler.start()
    # exec the script.
    try:
        exec_(code, globals_)
    except:
        # don't profile print_exc().
        profiler.stop()
        traceback.print_exc()
    else:
        profiler.stop()
    if PY2:
        # in Python 2, exec's cpu time is duplicated with actual cpu time.
        stat = profiler.stats.get_child(frame.f_code)
        stat.remove_child(exec_.func_code)
    if dump_filename is None:
        # show the result using a viewer.
        viewer, loop = make_viewer(mono)
        viewer.set_stats(profiler.stats)
        try:
            loop.run()
        except KeyboardInterrupt:
            pass
    else:
        # save the result.
        stats = profiler.result()
        with open(dump_filename, 'w') as f:
            pickle.dump(stats, f, pickle_protocol)
        click.echo('To view statistics:')
        click.echo('  $ python -m profiling view ', nl=False)
        click.secho(dump_filename, underline=True)


@main.command('live-profile')
@live_profiler_params
@viewer_params
def live_profile(script, timer, interval, pickle_protocol, mono):
    filename, code, globals_ = script
    sys.argv[:] = [filename]
    parent_sock, child_sock = socket.socketpair()
    pid = os.fork()
    if pid == 0:
        # child
        devnull = os.open(os.devnull, os.O_RDWR)
        for f in [sys.stdin, sys.stdout, sys.stderr]:
            os.dup2(devnull, f.fileno())
        frame = sys._getframe()
        profiler = BackgroundProfiler(timer, frame, code)
        profiler.prepare()
        server_args = (noop, interval, pickle_protocol)
        server = SelectProfilingServer(None, profiler, *server_args)
        server.clients.add(child_sock)
        spawn_thread(server.connected, child_sock)
        try:
            exec_(code, globals_)
        finally:
            child_sock.close()
    else:
        # parent
        viewer, loop = make_viewer(mono)
        client = ProfilingClient(viewer, loop.event_loop, parent_sock)
        client.start()
        try:
            loop.run()
        except KeyboardInterrupt:
            pass
        finally:
            parent_sock.close()
            os.kill(pid, signal.SIGINT)


@main.command('remote-profile')
@live_profiler_params
@click.option('-b', '--bind', 'addr', type=Address(), default=':8912',
              help='IP address to serve profiling results.')
@click.option('--start-signo', type=SignalNumber(), default=signal.SIGUSR1)
@click.option('--stop-signo', type=SignalNumber(), default=signal.SIGUSR2)
@click.option('-v', '--verbose', is_flag=True,
              help='Print profiling server logs.')
def remote_profile(script, timer, interval, pickle_protocol,
                   addr, start_signo, stop_signo, verbose):
    """Launch a server to profile continuously."""
    filename, code, globals_ = script
    sys.argv[:] = [filename]
    # create listener.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(addr)
    listener.listen(1)
    # be verbose or quiet.
    if verbose:
        log = lambda x: click.echo(click.style(' > ', fg='cyan') + x)
        bound_addr = listener.getsockname()
        log('Listening on {0}:{1} for profiling...'.format(*bound_addr))
    else:
        log = noop
    # start profiling server.
    frame = sys._getframe()
    profiler = BackgroundProfiler(timer, frame, code, start_signo, stop_signo)
    profiler.prepare()
    server_args = (log, interval, pickle_protocol)
    server = SelectProfilingServer(listener, profiler, *server_args)
    spawn_thread(server.serve_forever)
    # exec the script.
    try:
        exec_(code, globals_)
    except KeyboardInterrupt:
        pass


@main.command()
@click.argument('src', type=ViewSource())
@click.option('--timeout', type=float, default=10)
@viewer_params
def view(src, timeout, mono):
    """Inspect statistics by TUI view."""
    src_type, src_name = src
    viewer, loop = make_viewer(mono)
    if src_type == 'dump':
        with open(src_name) as f:
            stats = pickle.load(f)
        src_time = datetime.fromtimestamp(os.path.getmtime(src_name))
        viewer.set_stats(stats, src_name, src_time)
    elif src_type in ('tcp', 'sock'):
        family = {'tcp': socket.AF_INET, 'sock': socket.AF_UNIX}[src_type]
        client = FailoverProfilingClient(viewer, loop.event_loop,
                                         src_name, family, timeout=timeout)
        client.start()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass


# profiling clients for urwid


class ProfilingClient(object):
    """A client of profiling server which is running behind the `Urwid`_ event
    loop.

    .. _Urwid: http://urwid.org/

    """

    def __init__(self, viewer, event_loop, sock):
        self.viewer = viewer
        self.event_loop = event_loop
        self.sock = sock

    def start(self):
        self.viewer.activate()
        self.event_loop.watch_file(self.sock.fileno(), self.handle)

    def handle(self):
        self.viewer.activate()
        try:
            stats = recv_stats(self.sock)
        except socket.error as exc:
            self.erred(exc.errno)
            return
        self.set_stats(stats)

    def erred(self, errno):
        self.viewer.inactivate()

    def set_stats(self, stats):
        src_time = datetime.now()
        self.viewer.set_stats(stats, src_time=src_time)


class FailoverProfilingClient(ProfilingClient):

    def __init__(self, viewer, event_loop, addr=None,
                 sock_family=socket.AF_INET, sock_type=socket.SOCK_STREAM,
                 timeout=None):
        self.addr = addr
        self.sockopts = (sock_family, sock_type)
        self.timeout = timeout
        super(FailoverProfilingClient, self).__init__(viewer, event_loop, None)

    def connect(self):
        errno = self.sock.connect_ex(self.addr)
        if errno == 0:
            # connected immediately.
            pass
        elif errno == 115:
            # will be connected.
            pass
        elif errno == 2:
            # no such socket file.
            self.event_loop.alarm(1, self.create_connection)
            return
        else:
            raise ValueError('Unexpected socket errno: {0}'.format(errno))
        self.event_loop.watch_file(self.sock.fileno(), self.handle)

    def disconnect(self, errno):
        self.event_loop.remove_watch_file(self.sock.fileno())
        self.sock.close()
        # try to reconnect.
        self.create_connection(1 if errno == 111 else 0)

    def create_connection(self, delay=0):
        self.sock = socket.socket(*self.sockopts)
        self.sock.setblocking(0)
        self.event_loop.alarm(delay, self.connect)

    def start(self):
        self.create_connection()

    def handle(self):
        self.event_loop.remove_alarm(getattr(self, '_t', None))
        super(FailoverProfilingClient, self).handle()
        self._t = self.event_loop.alarm(self.timeout, self.viewer.inactivate)

    def erred(self, errno):
        super(FailoverProfilingClient, self).erred(errno)
        self.disconnect(errno)

    def set_stats(self, stats):
        src_time = datetime.now()
        self.viewer.set_stats(stats, self.addr, src_time)


if __name__ == '__main__':
    main()
