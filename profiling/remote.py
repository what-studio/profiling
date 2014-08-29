# -*- coding: utf-8 -*-
"""
    profiling.remote
    ~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
import io
from logging import getLogger as get_logger
try:
    import cPickle as pickle
except ImportError:
    import pickle
import struct

import gevent
from gevent import socket
from gevent.server import StreamServer


__all__ = ['recv_stats', 'ProfilerServer']


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


class ProfilerServer(StreamServer):

    greenlet = None
    log = LOGGER.debug

    def __init__(self, listener, profiler, interval=5, **kwargs):
        super(ProfilerServer, self).__init__(listener, spawn=None, **kwargs)
        self.profiler = profiler
        self.interval = interval
        self.connections = set()
        self.dump = io.BytesIO()

    def add_connection(self, connection):
        self.connections.add(connection)
        if len(self.connections) == 1 and self.greenlet is None:
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
        try:
            self.send(connection, self.dump)
        except socket.error:
            pass

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
            with open('.tmp/k1server.prof', 'w') as f:
                f.write(self.dump.getvalue())
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
        connection.send(struct.pack(SIZE_STRUCT_FORMAT, length))
        connection.send(buf.read())

    def broadcast(self, buf, length=None):
        if length is None:
            length = self._get_length(buf)
        for connection in list(self.connections):
            try:
                self.send(connection, buf, length)
            except socket.error:
                pass
