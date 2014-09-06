# -*- coding: utf-8 -*-
"""
    profiling.remote
    ~~~~~~~~~~~~~~~~

    Server and client implementation for remote profiling.

"""
from __future__ import absolute_import
import io
from logging import getLogger as get_logger
try:
    import cPickle as pickle
except ImportError:
    import pickle
import select
import struct
import time

import gevent
from gevent import socket
from gevent.lock import Semaphore
from gevent.server import StreamServer

from .profiler import Profiler


__all__ = ['recv_stats', 'start_server', 'ProfilerServer']


SIZE_STRUCT_FORMAT = '<Q'  # unsigned long long
LOGGER = get_logger('Profiling')


def recv_full_buffer(sock, size):
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
    buf = recv_full_buffer(sock, struct.calcsize(SIZE_STRUCT_FORMAT))
    size = struct.unpack(SIZE_STRUCT_FORMAT, buf.getvalue())[0]
    buf = recv_full_buffer(sock, size)
    stats = pickle.load(buf)
    return stats


def start_server(listener, profiler=None, interval=5, log=LOGGER.debug):
    """Starts the profiler server."""
    if profiler is None:
        profiler = Profiler()
    timeout_at = None
    conns = set()
    dump = io.BytesIO()
    while True:
        timeout = None if timeout_at is None else timeout_at - time.time()
        rlist, __, __ = select.select(conns.union([listener]), (), (), timeout)
        for sock in rlist:
            if sock is listener:
                # a new connection
                _connected(sock, conns, log, interval)
            else:
                # a connection closed
                _disconnected(sock, conns, log, profiler)
        if not conns:
            timeout_at = None
            continue
        now = time.time()
        # broadcast the profile result
        if timeout_at is not None and timeout_at < now:
            profiler.stop()
            _clear(dump)
            pickle.dump(profiler.frozen_stats(), dump)
            data = _pack(dump)
            for sock in conns:
                sock.sendall(data)
            timeout_at = None
        # start the profiler
        if timeout_at is None:
            timeout_at = now + interval
            profiler.clear()
            profiler.start()


def _connected(listener, conns, log, interval):
    sock, addr = listener.accept()
    conns.add(sock)
    num_conns = len(conns)
    if addr:
        fmt = 'Connected {0[0]}:{0[1]} (total: {1})'
    else:
        fmt = 'A client connected (total: {1})'
    log(fmt.format(addr, num_conns))
    if num_conns == 1:
        log('Profiling every {0} seconds...'.format(interval))


def _disconnected(sock, conns, log, profiler):
    addr = sock.getsockname()
    conns.remove(sock)
    sock.close()
    if addr:
        fmt = 'Disconnected from {0[0]}:{0[1]} (total: {1})'
    else:
        fmt = 'A client disconnected (total: {1})'
    log(fmt.format(addr, len(conns)))
    if not conns and profiler.is_running():
        profiler.stop()
        log('Profiling disabled')


def _clear(dump):
    dump.seek(0)
    dump.truncate(0)


def _pack(dump):
    dump.seek(0, io.SEEK_END)
    length = dump.tell()
    dump.seek(0)
    return struct.pack(SIZE_STRUCT_FORMAT, length) + dump.read()


class ProfilerServer(StreamServer):

    greenlet = None
    log = LOGGER.debug

    def __init__(self, listener, profiler, interval=5, **kwargs):
        super(ProfilerServer, self).__init__(listener, spawn=None, **kwargs)
        self.profiler = profiler
        self.interval = interval
        self.connections = set()
        self.dump = io.BytesIO()
        self.lock = Semaphore()

    def add_connection(self, connection):
        self.connections.add(connection)
        if self.greenlet is None and len(self.connections) == 1:
            self.greenlet = gevent.spawn(self.profile_forever)
            self.greenlet.link(lambda g: setattr(self, 'greenlet', None))

    def remove_connection(self, connection):
        self.connections.remove(connection)

    def handle(self, connection, address=None):
        self.add_connection(connection)
        num_connections = len(self.connections)
        if address:
            fmt = 'Connected {0} (total: {1})'
        else:
            fmt = 'A client connected (total: {1})'
        self.log(fmt.format(address, num_connections))
        gevent.spawn(self._detect_closing, connection, address)
        with self.lock:
            self.send(connection, self.dump)

    def _detect_closing(self, connection, address=None):
        while True:
            try:
                if connection.recv(128):
                    continue
            except socket.error:
                pass
            break
        self.remove_connection(connection)
        num_connections = len(self.connections)
        if address:
            fmt = 'Disconnected from {0} (total: {1})'
        else:
            fmt = 'A client disconnected (total: {1})'
        self.log(fmt.format(address, num_connections))

    def profile(self):
        self.profiler.clear()
        self.profiler.start()
        gevent.sleep(self.interval)
        self.profiler.stop()

    def profile_forever(self):
        self.log('Profiling every {0} seconds...'.format(self.interval))
        while self.connections:
            self.profile()
            self.dump.seek(0)
            self.dump.truncate(0)
            pickle.dump(self.profiler.frozen_stats(), self.dump)
            with self.lock:
                self.broadcast(self.dump)
        self.log('Profiling disabled')

    def _get_length(self, buf):
        buf.seek(0, io.SEEK_END)
        return buf.tell()

    def send(self, connection, buf, length=None):
        if length is None:
            length = self._get_length(buf)
        if not length:
            return
        buf.seek(0)
        connection.sendall(struct.pack(SIZE_STRUCT_FORMAT, length))
        connection.sendall(buf.read())

    def broadcast(self, buf, length=None):
        if length is None:
            length = self._get_length(buf)
        for connection in list(self.connections):
            try:
                self.send(connection, buf, length)
            except socket.error:
                pass
