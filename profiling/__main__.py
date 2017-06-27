# -*- coding: utf-8 -*-
"""
   profiling.__main__
   ~~~~~~~~~~~~~~~~~~

   The command-line interface to profile a script or view profiling results.

   .. sourcecode:: console

      $ profiling --help

   :copyright: (c) 2014-2017, What! Studio
   :license: BSD, see LICENSE for more details.

"""
from __future__ import absolute_import

from datetime import datetime
from functools import partial, wraps
import importlib
import os
try:
    import cPickle as pickle
except ImportError:
    import pickle
import runpy
import signal
import socket
from stat import S_ISREG, S_ISSOCK
import sys
import threading
import time
import traceback

import click
from click_default_group import DefaultGroup
from six import exec_
from six.moves import builtins
from six.moves.configparser import ConfigParser, NoOptionError, NoSectionError

from profiling import remote, sampling, tracing
from profiling.__about__ import __version__
from profiling.profiler import Profiler
from profiling.remote.background import BackgroundProfiler
from profiling.remote.client import FailoverProfilingClient, ProfilingClient
from profiling.remote.select import SelectProfilingServer
from profiling.sampling import samplers, SamplingProfiler
from profiling.tracing import timers, TracingProfiler
from profiling.viewer import bind_game_keys, bind_vim_keys, StatisticsViewer


__all__ = ['cli', 'profile', 'view']


DEFAULT_ENDPOINT = '127.0.0.1:8912'


class ProfilingCLI(DefaultGroup):

    def __init__(self, *args, **kwargs):
        super(ProfilingCLI, self).__init__(*args, **kwargs)
        self.command_name_aliases = {}

    def command(self, *args, **kwargs):
        """Usage::

           @cli.command(aliases=['ci'])
           def commit():
               ...

        """
        aliases = kwargs.pop('aliases', None)
        decorator = super(ProfilingCLI, self).command(*args, **kwargs)
        if aliases is None:
            return decorator
        def _decorator(f):
            cmd = decorator(f)
            for alias in aliases:
                self.command_name_aliases[alias] = cmd.name
            return cmd
        return _decorator

    def get_command(self, ctx, cmd_name):
        # Resolve alias.
        try:
            cmd_name = self.command_name_aliases[cmd_name]
        except KeyError:
            pass
        return super(ProfilingCLI, self).get_command(ctx, cmd_name)


@click.command('profiling', cls=ProfilingCLI, default='profile')
@click.version_option(__version__)
def cli():
    sys.path.insert(0, os.curdir)
    bind_vim_keys()
    bind_game_keys()


class read_config(object):
    """Reads a config once in a Click context."""

    filenames = ['setup.cfg', '.profiling']
    ctx_and_config = (None, None)

    def __new__(cls):
        ctx, config = cls.ctx_and_config
        current_ctx = click.get_current_context(silent=True)
        if current_ctx != ctx:
            config = ConfigParser()
            config.read(cls.filenames)
            cls.ctx_and_config = (current_ctx, config)
        return config


def option_getter(type):
    """Gets an unbound method to get a configuration option as the given type.
    """
    option_getters = {None: ConfigParser.get,
                      int: ConfigParser.getint,
                      float: ConfigParser.getfloat,
                      bool: ConfigParser.getboolean}
    return option_getters.get(type, option_getters[None])


def config_default(option, default=None, type=None, section=cli.name):
    """Guesses a default value of a CLI option from the configuration.

    ::

       @click.option('--locale', default=config_default('locale'))

    """
    def f(option=option, default=default, type=type, section=section):
        config = read_config()
        if type is None and default is not None:
            # detect type from default.
            type = builtins.type(default)
        get_option = option_getter(type)
        try:
            return get_option(config, section, option)
        except (NoOptionError, NoSectionError):
            return default
    return f


def config_flag(option, value, default=False, section=cli.name):
    """Guesses whether a CLI flag should be turned on or off from the
    configuration.  If the configuration option value is same with the given
    value, it returns ``True``.

    ::

       @click.option('--ko-kr', 'locale', is_flag=True,
                     default=config_flag('locale', 'ko_KR'))

    """
    class x(object):
        def __bool__(self, option=option, value=value,
                     default=default, section=section):
            config = read_config()
            type = builtins.type(value)
            get_option = option_getter(type)
            try:
                return get_option(config, section, option) == value
            except (NoOptionError, NoSectionError):
                return default
        __nonzero__ = __bool__
    return x()


def get_title(src_name, src_type=None):
    """Normalizes a source name as a string to be used for viewer's title."""
    if src_type == 'tcp':
        return '{0}:{1}'.format(*src_name)
    return os.path.basename(src_name)


def make_viewer(mono=False, *loop_args, **loop_kwargs):
    """Makes a :class:`profiling.viewer.StatisticsViewer` with common options.
    """
    viewer = StatisticsViewer()
    loop = viewer.loop(*loop_args, **loop_kwargs)
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

    - `threading`
    - `greenlet`
    - `eventlet`

    """
    if mode is None:
        # 'threading' is the default mode.
        mode = 'threading'
    elif mode not in spawn.modes:
        # validate the given mode.
        raise ValueError('Invalid spawn mode: %s' % mode)
    if mode == 'threading':
        return spawn_thread(func, *args, **kwargs)
    elif mode == 'gevent':
        import gevent
        import gevent.monkey
        gevent.monkey.patch_select()
        gevent.monkey.patch_socket()
        return gevent.spawn(func, *args, **kwargs)
    elif mode == 'eventlet':
        import eventlet
        eventlet.patcher.monkey_patch(select=True, socket=True)
        return eventlet.spawn(func, *args, **kwargs)
    assert False


spawn.modes = ['threading', 'gevent', 'eventlet']


#: Just returns the first argument.
noop = lambda x: x


def import_(module_name, name):
    """Imports an object by a relative module path::

       Profiler = import_('profiling.profiler', 'Profiler')

    """
    module = importlib.import_module(module_name, __package__)
    return getattr(module, name)


#: Makes a function which import an object by :func:`import_` lazily.
importer = lambda module_name, name: partial(import_, module_name, name)


# custom parameter types


class Class(click.ParamType):

    def __init__(self, modules, base, base_name=None, postfix=True):
        self.modules = modules
        self.base = base
        self.base_name = base_name
        self.postfix = postfix

    def convert(self, value, param, ctx):
        if value == self.base_name:
            return self.base
        name = value.title()
        if self.postfix:
            name += self.base.__name__.title()
        for mod in self.modules:
            try:
                cls = getattr(mod, name)
            except AttributeError:
                continue
            if not isinstance(cls, type):
                continue
            elif not issubclass(cls, self.base):
                continue
            return cls
        self.fail('%s not found' % name)

    def get_metavar(self, param):
        return self.base.__name__.upper()


class Script(click.File):
    """A parameter type for Python script."""

    def __init__(self):
        super(Script, self).__init__('rb')

    def convert(self, value, param, ctx):
        with super(Script, self).convert(value, param, ctx) as f:
            filename = f.name
            code = compile(f.read(), filename, 'exec')
            globals_ = {'__file__': filename, '__name__': '__main__',
                        '__package__': None, '__doc__': None}
        return (filename, code, globals_)

    def get_metavar(self, param):
        return 'PYTHON'


class Module(click.ParamType):

    def convert(self, value, param, ctx):
        # inspired by @htch's fork.
        # https://github.com/htch/profiling/commit/4a4eb6e
        try:
            detail = runpy._get_module_details(value)
        except ImportError as exc:
            ctx.fail(str(exc))
        try:
            # since Python 3.4.
            mod_name, mod_spec, code = detail
        except ValueError:
            mod_name, loader, code, filename = detail
        else:
            loader = mod_spec.loader
            filename = mod_spec.origin
        # follow runpy's behavior.
        pkg_name = mod_name.rpartition('.')[0]
        globals_ = sys.modules['__main__'].__dict__.copy()
        globals_.update(__name__='__main__', __file__=filename,
                        __loader__=loader, __package__=pkg_name)
        return (filename, code, globals_)

    def get_metavar(self, param):
        return 'PYTHON-MODULE'


class Command(click.ParamType):

    def convert(self, value, param, ctx):
        filename = '<string>'
        code = compile(value, filename, 'exec')
        globals_ = {'__name__': '__main__',
                    '__package__': None, '__doc__': None}
        return (filename, code, globals_)

    def get_metavar(self, param):
        return 'PYTHON-COMMAND'


class Endpoint(click.ParamType):
    """A parameter type for IP endpoint."""

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
                src_name = Endpoint().convert(value, param, ctx)
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
            raise ValueError('Dump file or socket address required.')
        return (src_type, src_name)

    def get_metavar(self, param):
        return 'SOURCE'


class SignalNumber(click.ParamType):
    """A parameter type for signal number."""

    @staticmethod
    def name_of(signum):
        for name, value in signal.__dict__.items():
            if signum == value:
                if name.startswith('SIG') and not name.startswith('SIG_'):
                    return name
        return str(signum)

    def convert(self, value, param, ctx):
        if isinstance(value, int):
            return value
        elif value.isdigit():
            return int(value)
        signame = value.upper()
        if not signame.startswith('SIG'):
            signame = 'SIG' + signame
        if signame.startswith('SIG_'):
            self.fail('Invalid signal %s' % signame)
        try:
            signum = getattr(signal, signame)
        except AttributeError:
            self.fail('Unknown signal %s' % signame)
        return signum

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
        return self.__class__(self.params + params)


def profiler_options(f):
    # tracing profiler options
    @click.option(
        '-T', '--tracing', 'import_profiler_class',
        flag_value=importer('profiling.tracing', 'TracingProfiler'),
        default=config_flag('profiler', 'tracing', True),
        help='Use tracing profiler. (default)')
    @click.option(
        '--timer', 'timer_class',
        type=Class([timers], timers.Timer, 'basic'),
        default=config_default('timer', 'basic'),
        help='Choose CPU timer for tracing profiler. (basic|thread|greenlet)')
    # sampling profiler options
    @click.option(
        '-S', '--sampling', 'import_profiler_class',
        flag_value=importer('profiling.sampling', 'SamplingProfiler'),
        default=config_flag('profiler', 'sampling', False),
        help='Use sampling profiler.')
    @click.option(
        '--sampler', 'sampler_class',
        type=Class([samplers], samplers.Sampler),
        default=config_default('sampler', 'itimer'),
        help='Choose frames sampler for sampling profiler. (itimer|tracing)')
    @click.option(
        '--sampling-interval', type=float,
        default=config_default('sampling-interval', samplers.INTERVAL),
        help='How often sample. (default: %.3f cpu sec)' % samplers.INTERVAL)
    # etc
    @click.option(
        '--pickle-protocol', type=int,
        default=config_default('pickle-protocol', remote.PICKLE_PROTOCOL),
        help='Pickle protocol to dump result.')
    @wraps(f)
    def wrapped(import_profiler_class, timer_class, sampler_class,
                sampling_interval, **kwargs):
        profiler_class = import_profiler_class()
        assert issubclass(profiler_class, Profiler)
        if issubclass(profiler_class, TracingProfiler):
            # profiler requires timer.
            timer_class = timer_class or tracing.TIMER_CLASS
            timer = timer_class()
            profiler_kwargs = {'timer': timer}
        elif issubclass(profiler_class, SamplingProfiler):
            sampler_class = sampler_class or sampling.SAMPLER_CLASS
            sampler = sampler_class(sampling_interval)
            profiler_kwargs = {'sampler': sampler}
        else:
            profiler_kwargs = {}
        profiler_factory = partial(profiler_class, **profiler_kwargs)
        return f(profiler_factory=profiler_factory, **kwargs)
    return wrapped


def profiler_arguments(f):
    @click.argument('argv', nargs=-1)
    @click.option('-m', 'module', type=Module(),
                  help='Run library module as a script.')
    @click.option('-c', 'command', type=Command(),
                  help='Program passed in as string.')
    @wraps(f)
    def wrapped(argv, module, command, **kwargs):
        if module is not None and command is not None:
            raise click.UsageError('Option -m and -c are exclusive')
        script = module or command
        if script is None:
            # -m and -c not passed.
            try:
                script_filename, argv = argv[0], argv[1:]
            except IndexError:
                raise click.UsageError('Script not specified')
            script = Script().convert(script_filename, None, None)
        kwargs.update(script=script, argv=argv)
        return f(**kwargs)
    return wrapped


viewer_options = Params([
    click.option('--mono', is_flag=True, help='Disable coloring.'),
])
onetime_profiler_options = Params([
    click.option(
        '-d', '--dump', 'dump_filename', type=click.Path(writable=True),
        help='Profiling result dump filename.'),
])
live_profiler_options = Params([
    click.option(
        '-i', '--interval', type=float,
        default=config_default('interval', remote.INTERVAL),
        help='How often update result. (default: %.0f sec)' % remote.INTERVAL),
    click.option(
        '--spawn', type=click.Choice(spawn.modes),
        default=config_default('spawn'),
        callback=lambda c, p, v: partial(spawn, v),
        help='How to spawn profiler server in background.'),
    click.option(
        '--signum', type=SignalNumber(),
        default=config_default('signum', BackgroundProfiler.signum),
        help=(
            'For communication between server and application. (default: %s)' %
            SignalNumber.name_of(BackgroundProfiler.signum)
        ))
])


# sub-commands


def __profile__(filename, code, globals_, profiler_factory,
                pickle_protocol=remote.PICKLE_PROTOCOL, dump_filename=None,
                mono=False):
    frame = sys._getframe()
    profiler = profiler_factory(base_frame=frame, base_code=code)
    profiler.start()
    try:
        exec_(code, globals_)
    except:
        # don't profile print_exc().
        profiler.stop()
        traceback.print_exc()
    else:
        profiler.stop()
    # discard this __profile__ function from the result.
    profiler.stats.discard_child(frame.f_code)
    if dump_filename is None:
        try:
            profiler.run_viewer(get_title(filename), mono=mono)
        except KeyboardInterrupt:
            pass
    else:
        result = profiler.result()
        with open(dump_filename, 'wb') as f:
            pickle.dump((profiler.__class__, result), f, pickle_protocol)
        click.echo('To view statistics:')
        click.echo('  $ profiling view ', nl=False)
        click.secho(dump_filename, underline=True)


class ProfilingCommand(click.Command):

    def collect_usage_pieces(self, ctx):
        """Prepend "[--]" before "[ARGV]..."."""
        pieces = super(ProfilingCommand, self).collect_usage_pieces(ctx)
        assert pieces[-1] == '[ARGV]...'
        pieces.insert(-1, 'SCRIPT')
        pieces.insert(-1, '[--]')
        return pieces


@cli.command(cls=ProfilingCommand)
@profiler_arguments
@profiler_options
@onetime_profiler_options
@viewer_options
def profile(script, argv, profiler_factory,
            pickle_protocol, dump_filename, mono):
    """Profile a Python script."""
    filename, code, globals_ = script
    sys.argv[:] = [filename] + list(argv)
    __profile__(filename, code, globals_, profiler_factory,
                pickle_protocol=pickle_protocol, dump_filename=dump_filename,
                mono=mono)


@cli.command('live-profile', aliases=['live'], cls=ProfilingCommand)
@profiler_arguments
@profiler_options
@live_profiler_options
@viewer_options
def live_profile(script, argv, profiler_factory, interval, spawn, signum,
                 pickle_protocol, mono):
    """Profile a Python script continuously."""
    filename, code, globals_ = script
    sys.argv[:] = [filename] + list(argv)
    parent_sock, child_sock = socket.socketpair()
    stderr_r_fd, stderr_w_fd = os.pipe()
    pid = os.fork()
    if pid:
        # parent
        os.close(stderr_w_fd)
        viewer, loop = make_viewer(mono)
        # loop.screen._term_output_file = open(os.devnull, 'w')
        title = get_title(filename)
        client = ProfilingClient(viewer, loop.event_loop, parent_sock, title)
        client.start()
        try:
            loop.run()
        except KeyboardInterrupt:
            os.kill(pid, signal.SIGINT)
        except:
            # unexpected profiler error.
            os.kill(pid, signal.SIGTERM)
            raise
        finally:
            parent_sock.close()
        # get exit code of child.
        w_pid, status = os.waitpid(pid, os.WNOHANG)
        if w_pid == 0:
            os.kill(pid, signal.SIGTERM)
        exit_code = os.WEXITSTATUS(status)
        # print stderr of child.
        with os.fdopen(stderr_r_fd, 'r') as f:
            child_stderr = f.read()
        if child_stderr:
            sys.stdout.flush()
            sys.stderr.write(child_stderr)
        # exit with exit code of child.
        sys.exit(exit_code)
    else:
        # child
        os.close(stderr_r_fd)
        # mute stdin, stdout.
        devnull = os.open(os.devnull, os.O_RDWR)
        for f in [sys.stdin, sys.stdout]:
            os.dup2(devnull, f.fileno())
        # redirect stderr to parent.
        os.dup2(stderr_w_fd, sys.stderr.fileno())
        frame = sys._getframe()
        profiler = profiler_factory(base_frame=frame, base_code=code)
        profiler_trigger = BackgroundProfiler(profiler, signum)
        profiler_trigger.prepare()
        server_args = (interval, noop, pickle_protocol)
        server = SelectProfilingServer(None, profiler_trigger, *server_args)
        server.clients.add(child_sock)
        spawn(server.connected, child_sock)
        try:
            exec_(code, globals_)
        finally:
            os.close(stderr_w_fd)
            child_sock.shutdown(socket.SHUT_WR)


@cli.command('remote-profile', aliases=['remote'], cls=ProfilingCommand)
@profiler_arguments
@profiler_options
@live_profiler_options
@click.option('-b', '--bind', 'endpoint', type=Endpoint(),
              default=config_default('endpoint', DEFAULT_ENDPOINT),
              help='IP endpoint to serve profiling results.')
@click.option('-v', '--verbose', is_flag=True,
              help='Print profiling server logs.')
def remote_profile(script, argv, profiler_factory, interval, spawn, signum,
                   pickle_protocol, endpoint, verbose):
    """Launch a server to profile continuously.  The default endpoint is
    127.0.0.1:8912.
    """
    filename, code, globals_ = script
    sys.argv[:] = [filename] + list(argv)
    # create listener.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(endpoint)
    listener.listen(1)
    # be verbose or quiet.
    if verbose:
        log = lambda x: click.echo(click.style('> ', fg='cyan') + x)
        bound_addr = listener.getsockname()
        log('Listening on {0}:{1} for profiling...'.format(*bound_addr))
    else:
        log = noop
    # start profiling server.
    frame = sys._getframe()
    profiler = profiler_factory(base_frame=frame, base_code=code)
    profiler_trigger = BackgroundProfiler(profiler, signum)
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
@click.argument('src', type=ViewerSource(),
                default=config_default('endpoint', DEFAULT_ENDPOINT))
@viewer_options
def view(src, mono):
    """Inspect statistics by TUI view."""
    src_type, src_name = src
    title = get_title(src_name, src_type)
    viewer, loop = make_viewer(mono)
    if src_type == 'dump':
        time = datetime.fromtimestamp(os.path.getmtime(src_name))
        with open(src_name, 'rb') as f:
            profiler_class, (stats, cpu_time, wall_time) = pickle.load(f)
        viewer.set_profiler_class(profiler_class)
        viewer.set_result(stats, cpu_time, wall_time, title=title, at=time)
        viewer.activate()
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
                   profiler_factory, pickle_protocol, dump_filename, mono,
                   **_ignored):
    """Profile a Python statement like timeit."""
    del _ignored
    globals_ = {}
    exec_(setup, globals_)
    if number is None:
        # determine number so that 0.2 <= total time < 2.0 like timeit.
        dummy_profiler = profiler_factory()
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
    __profile__(stmt, code, globals_, profiler_factory,
                pickle_protocol=pickle_protocol, dump_filename=dump_filename,
                mono=mono)


# Deprecated.
main = cli


if __name__ == '__main__':
    cli(prog_name='python -m profiling')
