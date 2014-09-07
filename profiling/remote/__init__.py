# -*- coding: utf-8 -*-
"""
    profiling.remote
    ~~~~~~~~~~~~~~~~

    Utilities for remote profiling.  They help you to implement profiling
    server and client.

"""
from __future__ import absolute_import
import functools
import io
from logging import getLogger as get_logger
try:
    import cPickle as pickle
except ImportError:
    import pickle
import socket
import struct

from ..profiler import Profiler


__all__ = ['LOGGER', 'LOG', 'INTERVAL', 'PICKLE_PROTOCOL',
           'SIZE_STRUCT_FORMAT', 'pack_stats', 'recv_exactly', 'recv_stats',
           'fmt_connected', 'fmt_disconnected', 'fmt_profiler_started',
           'fmt_profiler_stopped', 'BaseProfilingServer']


#: The standard logger.
LOGGER = get_logger('Profiling')

#: The standard log function.
LOG = LOGGER.debug

#: The default profiling interval.
INTERVAL = 5

#: The default Pickle protocol.
PICKLE_PROTOCOL = getattr(pickle, 'DEFAULT_PROTOCOL', pickle.HIGHEST_PROTOCOL)

#: The struct format to pack packet size. (uint32)
SIZE_STRUCT_FORMAT = '!I'


def pack_stats(profiler, pickle_protocol=PICKLE_PROTOCOL):
    """Packs statistics from the profiler by Pickle with size as a header."""
    dump = io.BytesIO()
    stats = profiler.result()
    pickle.dump(stats, dump, pickle_protocol)
    size = dump.tell()
    return struct.pack(SIZE_STRUCT_FORMAT, size) + dump.getvalue()


def recv_exactly(sock, size):
    """Receives exactly `size` bytes.  This function blocks the thread."""
    buf = io.BytesIO()
    while True:
        size_required = size - buf.tell()
        if not size_required:
            break
        data = sock.recv(size_required)
        if not data:
            raise socket.error(54, 'Connection closed')
        buf.write(data)
    buf.seek(0)
    return buf


def recv_stats(sock):
    """Receives statistics from the socket.  This function blocks the thread.
    """
    buf = recv_exactly(sock, struct.calcsize(SIZE_STRUCT_FORMAT))
    size = struct.unpack(SIZE_STRUCT_FORMAT, buf.getvalue())[0]
    buf = recv_exactly(sock, size)
    stats = pickle.load(buf)
    return stats


def fmt_connected(addr, num_clients):
    if addr:
        fmt = 'Connected from {0[0]}:{0[1]} (total: {1})'
    else:
        fmt = 'A client connected (total: {1})'
    return fmt.format(addr, num_clients)


def fmt_disconnected(addr, num_clients):
    if addr:
        fmt = 'Disconnected from {0[0]}:{0[1]} (total: {1})'
    else:
        fmt = 'A client disconnected (total: {1})'
    return fmt.format(addr, num_clients)


def fmt_profiler_started(interval):
    return 'Profiling every {0} seconds...'.format(interval)


def fmt_profiler_stopped():
    return 'Profiler stopped'


def abstract(message):
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            raise NotImplementedError(message)
        return wrapped
    return decorator


class BaseProfilingServer(object):
    """The base class for profiling server implementations.  Implement abstract
    methods and call :meth:`connected` when a client connected.
    """

    _latest_data = None

    def __init__(self, profiler=None, log=LOG,
                 interval=INTERVAL, pickle_protocol=PICKLE_PROTOCOL):
        super(BaseProfilingServer, self).__init__()
        if profiler is None:
            profiler = Profiler()
        self.profiler = profiler
        self.log = log
        self.interval = interval
        self.pickle_protocol = pickle_protocol
        self.clients = set()

    @abstract('Implement serve_forever() to run a server synchronously.')
    def serve_forever(self):
        pass

    @abstract('Implement _send() to send data to the client.')
    def _send(self, client, data):
        pass

    @abstract('Implement _close() to close the client.')
    def _close(self, client):
        pass

    @abstract('Implement _addr() to get the address from the client.')
    def _addr(self, client):
        pass

    @abstract('Implement _start_profiling() to start a profiling loop.')
    def _start_profiling(self):
        pass

    @abstract('Implement _start_watching() to add a disconnection callback to '
              'the client')
    def _start_watching(self, client):
        pass

    def profiling(self):
        """A generator which profiles then broadcasts the result.  Implement
        sleeping loop using this::

           def profile_periodically(self):
               for __ in self.profiling():
                   time.sleep(self.interval)

        """
        self._log_profiler_started()
        while self.clients:
            self.profiler.start()
            # should sleep
            yield
            self.profiler.stop()
            data = pack_stats(self.profiler, self.pickle_protocol)
            self._latest_data = data
            self.profiler.clear()
            # broadcast
            for client in self.clients:
                self._send(client, data)
            del data
        self._log_profiler_stopped()

    def connected(self, client):
        """Call this method when a client connected."""
        self.clients.add(client)
        self._log_connected(client)
        self._start_watching(client)
        if self._latest_data is not None:
            self._send(client, self._latest_data)
        if len(self.clients) == 1:
            self._start_profiling()

    def disconnected(self, client):
        """Call this method when a client disconnected."""
        self.clients.remove(client)
        self._log_disconnected(client)
        self._close(client)

    def _log_connected(self, client):
        addr = self._addr(client)
        addr = addr if isinstance(addr, tuple) else None
        self.log(fmt_connected(addr, len(self.clients)))

    def _log_disconnected(self, client):
        addr = self._addr(client)
        addr = addr if isinstance(addr, tuple) else None
        self.log(fmt_disconnected(addr, len(self.clients)))

    def _log_profiler_started(self):
        self.log(fmt_profiler_started(self.interval))

    def _log_profiler_stopped(self):
        self.log(fmt_profiler_stopped())
