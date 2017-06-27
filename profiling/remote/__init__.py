# -*- coding: utf-8 -*-
"""
   profiling.remote
   ~~~~~~~~~~~~~~~~

   Utilities for remote profiling.  They help you to implement profiling
   server and client.

   :copyright: (c) 2014-2017, What! Studio
   :license: BSD, see LICENSE for more details.

"""
from __future__ import absolute_import

from errno import EBADF, ECONNRESET, EPIPE
import functools
import io
from logging import getLogger as get_logger
try:
    import cPickle as pickle
except ImportError:
    import pickle
import socket
import struct

from profiling.__about__ import __version__


__all__ = ['LOGGER', 'LOG', 'INTERVAL', 'PICKLE_PROTOCOL',
           'SIZE_STRUCT_FORMAT', 'pack_result', 'recv_msg', 'fmt_connected',
           'fmt_disconnected', 'fmt_profiler_started', 'fmt_profiler_stopped',
           'ProfilingServer']


#: The standard logger.
LOGGER = get_logger('Profiling')

#: The standard log function.
LOG = LOGGER.debug

#: The default profiling interval.
INTERVAL = 1

#: The default Pickle protocol.
PICKLE_PROTOCOL = getattr(pickle, 'DEFAULT_PROTOCOL', pickle.HIGHEST_PROTOCOL)

#: The struct format to pack message size. (uint32)
SIZE_STRUCT_FORMAT = '!I'

#: The struct format to pack method. (uint8)
METHOD_STRUCT_FORMAT = '!B'


# methods
WELCOME = 0x10
PROFILER = 0x11
RESULT = 0x12


def pack_msg(method, msg, pickle_protocol=PICKLE_PROTOCOL):
    """Packs a method and message."""
    dump = io.BytesIO()
    pickle.dump(msg, dump, pickle_protocol)
    size = dump.tell()
    return (struct.pack(METHOD_STRUCT_FORMAT, method) +
            struct.pack(SIZE_STRUCT_FORMAT, size) + dump.getvalue())


def recv(sock, size):
    """Receives exactly `size` bytes.  This function blocks the thread."""
    data = sock.recv(size, socket.MSG_WAITALL)
    if len(data) < size:
        raise socket.error(ECONNRESET, 'Connection closed')
    return data


def recv_msg(sock):
    """Receives a method and message from the socket.  This function blocks the
    current thread.
    """
    data = recv(sock, struct.calcsize(METHOD_STRUCT_FORMAT))
    method, = struct.unpack(METHOD_STRUCT_FORMAT, data)
    data = recv(sock, struct.calcsize(SIZE_STRUCT_FORMAT))
    size, = struct.unpack(SIZE_STRUCT_FORMAT, data)
    data = recv(sock, size)
    msg = pickle.loads(data)
    return method, msg


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


class ProfilingServer(object):
    """The base class for profiling server implementations.  Implement abstract
    methods and call :meth:`connected` when a client connected.
    """

    _latest_result_data = None

    def __init__(self, profiler, interval=INTERVAL,
                 log=LOG, pickle_protocol=PICKLE_PROTOCOL):
        self.profiler = profiler
        self.interval = interval
        self.log = log
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
            try:
                self.profiler.start()
            except RuntimeError:
                pass
            # should sleep.
            yield
            self.profiler.stop()
            result = self.profiler.result()
            data = pack_msg(RESULT, result,
                            pickle_protocol=self.pickle_protocol)
            self._latest_result_data = data
            # broadcast.
            closed_clients = []
            for client in self.clients:
                try:
                    self._send(client, data)
                except socket.error as exc:
                    if exc.errno == EPIPE:
                        closed_clients.append(client)
            del data
            # handle disconnections.
            for client in closed_clients:
                self.disconnected(client)
        self._log_profiler_stopped()

    def send_msg(self, client, method, msg, pickle_protocol=None):
        if pickle_protocol is None:
            pickle_protocol = self.pickle_protocol
        data = pack_msg(method, msg, pickle_protocol=pickle_protocol)
        self._send(client, data)

    def connected(self, client):
        """Call this method when a client connected."""
        self.clients.add(client)
        self._log_connected(client)
        self._start_watching(client)
        self.send_msg(client, WELCOME, (self.pickle_protocol, __version__),
                      pickle_protocol=0)
        profiler = self.profiler
        while True:
            try:
                profiler = profiler.profiler
            except AttributeError:
                break
        self.send_msg(client, PROFILER, type(profiler))
        if self._latest_result_data is not None:
            try:
                self._send(client, self._latest_result_data)
            except socket.error as exc:
                if exc.errno in (EBADF, EPIPE):
                    self.disconnected(client)
                    return
                raise
        if len(self.clients) == 1:
            self._start_profiling()

    def disconnected(self, client):
        """Call this method when a client disconnected."""
        if client not in self.clients:
            # already disconnected.
            return
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
