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
from functools import partial
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
import time
import traceback

import click
from six import PY2, exec_

from .profiler import Profiler
from .remote import INTERVAL, PICKLE_PROTOCOL, recv_stats
from .remote.background import SIGNUM, BackgroundProfilerTrigger
from .remote.errnos import ENOENT, ECONNREFUSED, EINPROGRESS
from .remote.select import SelectProfilingServer
from .viewer import StatisticsViewer


__all__ = ['cli', 'profile', 'view']


class AliasedGroup(click.Group):

    def __init__(self, *args, **kwargs):
        super(AliasedGroup, self).__init__(*args, **kwargs)
        self.aliases = {}

    def command(self, *args, **kwargs):
        """Usage::

           @group.command(aliases=['ci'])
           def commit():
               ...

        """
        aliases = kwargs.pop('aliases', None)
        decorator = super(AliasedGroup, self).command(*args, **kwargs)
        if aliases is None:
            return decorator
        def aliased_decorator(f):
            cmd = decorator(f)
            for alias in aliases:
                self.aliases[alias] = cmd
            return cmd
        return aliased_decorator

    def get_command(self, ctx, cmd_name):
        try:
            return self.aliases[cmd_name]
        except KeyError:
            return super(AliasedGroup, self).get_command(ctx, cmd_name)


@click.command(cls=AliasedGroup)
def cli():
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
    """Spawns a daemon thread."""
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()
    return thread


def spawn(mode, func, *args, **kwargs):
    """Spawns a thread-like object which runs the given function concurrently.

    Available modes:

    - `thread`
    - `greenlet`
    - `eventlet`

    """
    if mode is None:
        # 'thread' is the default mode.
        mode = 'thread'
    elif mode not in spawn.modes:
        # validate the given mode.
        raise ValueError('Invalid spawn mode: {0}'.format(mode))
    if mode == 'thread':
        return spawn_thread(func, *args, **kwargs)
    elif mode == 'gevent':
        import gevent
        return gevent.spawn(func, *args, **kwargs)
    elif mode == 'eventlet':
        import eventlet
        return eventlet.spawn(func, *args, **kwargs)
    assert False


spawn.modes = ['thread', 'gevent', 'eventlet']


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
        return 'SIGNUM'


# common parameters


class Params(object):

    def __init__(self, params):
        self.params = params

    def __call__(self, f):
        for param in self.params[::-1]:
            f = param(f)
        return f

    def __add__(self, params):
        return type(self)(self.params + params)


profiler_arguments = Params([
    click.argument('script', type=Script()),
    click.argument('argv', nargs=-1),
])
profiler_options = Params([
    click.option('-t', '--timer', type=Timer(),
                 help='Choose CPU time measurer.'),
    click.option('--pickle-protocol', type=int, default=PICKLE_PROTOCOL,
                 help='Pickle protocol to dump profiling result.'),
])
viewer_options = Params([
    click.option('--mono', is_flag=True, help='Disable coloring.'),
])
onetime_profiler_options = Params([
    click.option('-d', '--dump', 'dump_filename',
                 type=click.Path(writable=True),
                 help='Profiling result dump filename.'),
])
live_profiler_options = Params([
    click.option('-i', '--interval', type=float, default=INTERVAL,
                 help='How often update the profiling result.'),
    click.option('--spawn', type=click.Choice(spawn.modes),
                 callback=lambda c, p, v: partial(spawn, v)),
    click.option('--signum', type=SignalNumber(), default=SIGNUM),
])


# sub-commands


def __profile__(filename, code, globals_,
                timer=None, pickle_protocol=PICKLE_PROTOCOL,
                dump_filename=None, mono=False):
    frame = sys._getframe()
    profiler = Profiler(timer, top_frame=frame, top_code=code)
    profiler.start()
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
        viewer, loop = make_viewer(mono)
        viewer.set_stats(profiler.stats, get_title(filename))
        try:
            loop.run()
        except KeyboardInterrupt:
            pass
    else:
        stats = profiler.result()
        with open(dump_filename, 'wb') as f:
            pickle.dump(stats, f, pickle_protocol)
        click.echo('To view statistics:')
        click.echo('  $ python -m profiling view ', nl=False)
        click.secho(dump_filename, underline=True)


class ProfilingCommand(click.Command):

    def collect_usage_pieces(self, ctx):
        """Prepend "[--]" before "[ARGV]..."."""
        pieces = super(ProfilingCommand, self).collect_usage_pieces(ctx)
        assert pieces[-1] == '[ARGV]...'
        pieces.insert(-1, '[--]')
        return pieces


@cli.command(cls=ProfilingCommand)
@profiler_arguments
@profiler_options
@onetime_profiler_options
@viewer_options
def profile(script, argv, timer, pickle_protocol, dump_filename, mono):
    """Profile a Python script."""
    filename, code, globals_ = script
    sys.argv[:] = [filename] + list(argv)
    __profile__(filename, code, globals_,
                timer=timer, pickle_protocol=pickle_protocol,
                dump_filename=dump_filename, mono=mono)


@cli.command('live-profile', cls=ProfilingCommand)
@profiler_arguments
@profiler_options
@live_profiler_options
@viewer_options
def live_profile(script, argv, timer, interval, spawn, signum,
                 pickle_protocol, mono):
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
        from .sampling import SamplingProfiler
        profiler = SamplingProfiler(timer, frame, code)
        profiler_trigger = BackgroundProfilerTrigger(profiler, signum)
        profiler_trigger.prepare()
        server_args = (interval, noop, pickle_protocol)
        server = SelectProfilingServer(None, profiler_trigger, *server_args)
        server.clients.add(child_sock)
        spawn(server.connected, child_sock)
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


@cli.command('remote-profile', cls=ProfilingCommand)
@profiler_arguments
@profiler_options
@live_profiler_options
@click.option('-b', '--bind', 'addr', type=Address(), default='127.0.0.1:8912',
              help='IP address to serve profiling results.')
@click.option('-v', '--verbose', is_flag=True,
              help='Print profiling server logs.')
def remote_profile(script, argv, timer, interval, spawn, signum,
                   pickle_protocol, addr, verbose):
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
    profiler = Profiler(timer, frame, code)
    profiler_trigger = BackgroundProfilerTrigger(profiler, signum)
    profiler_trigger.prepare()
    server_args = (interval, log, pickle_protocol)
    server = SelectProfilingServer(listener, profiler_trigger, *server_args)
    spawn(server.serve_forever)
    # exec the script.
    try:
        exec_(code, globals_)
    except KeyboardInterrupt:
        pass


@cli.command()
@click.argument('src', type=ViewerSource())
@viewer_options
def view(src, mono):
    """Inspect statistics by TUI view."""
    src_type, src_name = src
    title = get_title(src_name, src_type)
    viewer, loop = make_viewer(mono)
    if src_type == 'dump':
        with open(src_name, 'rb') as f:
            stats = pickle.load(f)
        time = datetime.fromtimestamp(os.path.getmtime(src_name))
        viewer.set_stats(stats, title, time)
    elif src_type in ('tcp', 'sock'):
        family = {'tcp': socket.AF_INET, 'sock': socket.AF_UNIX}[src_type]
        client = FailoverProfilingClient(viewer, loop.event_loop,
                                         src_name, family, title=title)
        client.start()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass


@cli.command('timeit-profile', aliases=['timeit'])
@click.argument('stmt', metavar='STATEMENT', default='pass')
@click.option('-n', '--number', type=int,
              help='How many times to execute the statement.')
@click.option('-r', '--repeat', type=int, default=3,
              help='How many times to repeat the timer.')
@click.option('-s', '--setup', default='pass',
              help='Statement to be executed once initially.')
@click.option('-t', '--time', help='Ignored.')
@click.option('-c', '--clock', help='Ignored.')
@click.option('-v', '--verbose', help='Ignored.')
@profiler_options
@onetime_profiler_options
@viewer_options
def timeit_profile(stmt, number, repeat, setup,
                   timer, pickle_protocol, dump_filename, mono, **_ignored):
    """Profile a Python statement like timeit."""
    del _ignored
    sys.path.insert(0, os.curdir)
    globals_ = {}
    exec_(setup, globals_)
    if number is None:
        # determine number so that 0.2 <= total time < 2.0 like timeit.
        dummy_profiler = Profiler()
        dummy_profiler.start()
        for x in range(1, 10):
            number = 10 ** x
            t = time.time()
            for y in range(number):
                exec_(stmt, globals_)
            if time.time() - t >= 0.2:
                break
        dummy_profiler.stop()
        del dummy_profiler
    code = compile('for _ in range(%d): %s' % (number, stmt),
                   'STATEMENT', 'exec')
    __profile__(stmt, code, globals_,
                timer=timer, pickle_protocol=pickle_protocol,
                dump_filename=dump_filename, mono=mono)


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
        while True:
            errno = self.sock.connect_ex(self.addr)
            if errno == 0:
                break
        if not errno:
            # connected immediately.
            pass
        elif errno == EINPROGRESS:
            # will be connected.
            pass
        elif errno == ENOENT:
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
        delay = self.failover_interval if errno == ECONNREFUSED else 0
        self.create_connection(delay)

    def create_connection(self, delay=0):
        self.sock = socket.socket(self.family)
        self.sock.setblocking(0)
        self.event_loop.alarm(delay, self.connect)

    def start(self):
        self.create_connection()

    def erred(self, errno):
        super(FailoverProfilingClient, self).erred(errno)
        self.disconnect(errno)


# Deprecated.
main = cli


if __name__ == '__main__':
    cli(prog_name='python -m profiling')
