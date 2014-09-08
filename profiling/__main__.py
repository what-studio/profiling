# -*- coding: utf-8 -*-
"""
    profiling.__main__
    ~~~~~~~~~~~~~~~~~~

    The command-line interface to profile a script or view profiling results.

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
from .remote.background import START_SIGNO, STOP_SIGNO, BackgroundProfiler
from .remote.select import SelectProfilingServer
from .viewer import StatisticsViewer


__all__ = ['main', 'profile', 'view']


@click.group()
def main():
    pass


def get_title(src_name, src_type=None):
    """Normalizes a source name as a string to be used for viewer's title."""
    if src_type == 'tcp':
        return '{0}:{1}'.format(*src_name)
    return os.path.basename(src_name)


def make_viewer(mono=False):
    """Makes a :class:`profiling.viewer.StatisticsViewer` with common options.
    """
    viewer = StatisticsViewer()
    viewer.use_vim_command_map()
    viewer.use_game_command_map()
    loop = viewer.loop()
    if mono:
        loop.screen.set_terminal_properties(1)
    return (viewer, loop)


def spawn_thread(func, *args, **kwargs):
    """Spawns a daemon thread.  The thread executes the given function by the
    given arguments.
    """
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()
    return thread


#: Just returns the first argument.
noop = lambda x: x


# custom parameter types


class Script(click.File):
    """A parameter type for Python script."""

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
    """A parameter type to choose profiling timer."""

    timers = {
        # timer name: (timer module name, timer class name)
        None: ('.timers', 'Timer'),
        'thread': ('.timers.thread', 'ThreadTimer'),
        'yappi': ('.timers.thread', 'YappiTimer'),
        'greenlet': ('.timers.greenlet', 'GreenletTimer'),
    }

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
    """A parameter type for IP address."""

    def convert(self, value, param, ctx):
        host, port = value.split(':')
        port = int(port)
        return (host, port)

    def get_metavar(self, param):
        return 'HOST:PORT'


class ViewerSource(click.ParamType):
    """A parameter type for :class:`profiling.viewer.StatisticsViewer` source.
    """

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
    """A parameter type for signal number."""

    def __init__(self):
        super(SignalNumber, self).__init__(0, 255)

    def get_metavar(self, param):
        return 'SIGNO'


# common parameters


class Params(object):

    def __init__(self, params):
        self.params = params

    def __call__(self, f):
        for param in self.params[::-1]:
            f = param(f)
        return f

    def extend(self, params):
        return type(self)(self.params + params)


profiler_params = Params([
    click.argument('script', type=Script()),
    click.argument('argv', nargs=-1),
    click.option('-t', '--timer', type=Timer(),
                 help='Choose CPU time measurer.'),
    click.option('--pickle-protocol', type=int, default=PICKLE_PROTOCOL,
                 help='Pickle protocol to dump profiling result.'),
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
@click.option('-d', '--dump', 'dump_filename',
              type=click.Path(writable=True),
              help='Profiling result dump filename.')
@viewer_params
def profile(script, argv, timer, pickle_protocol, dump_filename, mono):
    """Profile a Python script."""
    filename, code, globals_ = script
    sys.argv[:] = [filename] + list(argv)
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
        viewer.set_stats(profiler.stats, get_title(filename))
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
def live_profile(script, argv, timer, interval, pickle_protocol, mono):
    """Profile a Python script continuously."""
    filename, code, globals_ = script
    sys.argv[:] = [filename] + list(argv)
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
        title = get_title(filename)
        client = ProfilingClient(viewer, loop.event_loop, parent_sock, title)
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
@click.option('-b', '--bind', 'addr', type=Address(), default='127.0.0.1:8912',
              help='IP address to serve profiling results.')
@click.option('--start-signo', type=SignalNumber(), default=START_SIGNO)
@click.option('--stop-signo', type=SignalNumber(), default=STOP_SIGNO)
@click.option('-v', '--verbose', is_flag=True,
              help='Print profiling server logs.')
def remote_profile(script, argv, timer, interval, pickle_protocol,
                   addr, start_signo, stop_signo, verbose):
    """Launch a server to profile continuously.  The default address is
    127.0.0.1:8912.
    """
    filename, code, globals_ = script
    sys.argv[:] = [filename] + list(argv)
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
@click.argument('src', type=ViewerSource())
@viewer_params
def view(src, mono):
    """Inspect statistics by TUI view."""
    src_type, src_name = src
    title = get_title(src_name, src_type)
    viewer, loop = make_viewer(mono)
    if src_type == 'dump':
        with open(src_name) as f:
            stats = pickle.load(f)
        time = datetime.fromtimestamp(os.path.getmtime(src_name))
        viewer.set_stats(stats, title, time)
    elif src_type in ('tcp', 'sock'):
        family = {'tcp': socket.AF_INET, 'sock': socket.AF_UNIX}[src_type]
        client = FailoverProfilingClient(
            viewer, loop.event_loop, src_name, family, title=title)
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

    def __init__(self, viewer, event_loop, sock, title=None):
        self.viewer = viewer
        self.event_loop = event_loop
        self.sock = sock
        self.title = title

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
        self.viewer.set_stats(stats, self.title, datetime.now())


class FailoverProfilingClient(ProfilingClient):
    """A profiling client but it tries to reconnect constantly."""

    failover_interval = 1

    def __init__(self, viewer, event_loop, addr=None, family=socket.AF_INET,
                 title=None):
        self.addr = addr
        self.family = family
        base = super(FailoverProfilingClient, self)
        base.__init__(viewer, event_loop, None, title)

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
            self.create_connection(self.failover_interval)
            return
        else:
            raise ValueError('Unexpected socket errno: {0}'.format(errno))
        self.event_loop.watch_file(self.sock.fileno(), self.handle)

    def disconnect(self, errno):
        self.event_loop.remove_watch_file(self.sock.fileno())
        self.sock.close()
        # try to reconnect.
        self.create_connection(self.failover_interval if errno == 111 else 0)

    def create_connection(self, delay=0):
        self.sock = socket.socket(self.family)
        self.sock.setblocking(0)
        self.event_loop.alarm(delay, self.connect)

    def start(self):
        self.create_connection()

    def erred(self, errno):
        super(FailoverProfilingClient, self).erred(errno)
        self.disconnect(errno)


if __name__ == '__main__':
    main()
