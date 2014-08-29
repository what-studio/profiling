# -*- coding: utf-8 -*-
"""
    profiling.remote
    ~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
import io
try:
    import cPickle as pickle
except ImportError:
    import pickle
import struct

import gevent
from gevent import socket
from gevent.server import StreamServer


SIZE_STRUCT_FORMAT = '<Q'  # unsigned long long


class ProfilerServer(StreamServer):

    greenlet = None

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

    def handle(self, connection, address):
        self.add_connection(connection)
        gevent.spawn(self._close_connection, connection)
        try:
            self.send(connection, self.dump)
        except socket.error:
            pass

    def _close_connection(self, connection):
        while True:
            try:
                if connection.recv(128):
                    continue
            except socket.error:
                pass
            self.remove_connection(connection)
            break

    def profile(self):
        print 'profile...'
        self.profiler.clear()
        self.profiler.start()
        gevent.sleep(self.interval)
        self.profiler.stop()

    def profile_forever(self):
        while self.connections:
            self.profile()
            self.dump.seek(0)
            self.dump.truncate(0)
            pickle.dump(self.profiler.frozen_stats(), self.dump)
            with open('.tmp/k1server.prof', 'w') as f:
                f.write(self.dump.getvalue())
            self.broadcast(self.dump)

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


class ProfilerClient(object):

    def __init__(self, connection):
        self.connection = connection

    def recv_stats(self):
        buf = self.recv_full_buffer(struct.calcsize(SIZE_STRUCT_FORMAT))
        size = struct.unpack(SIZE_STRUCT_FORMAT, buf.getvalue())[0]
        buf = self.recv_full_buffer(size)
        return pickle.load(buf)

    def recv_full_buffer(self, size):
        buf = io.BytesIO()
        while True:
            size_required = size - buf.tell()
            if not size_required:
                break
            data = self.connection.recv(size_required)
            if not data:
                raise socket.error(54, 'Connection closed')
            buf.write(data)
        buf.seek(0)
        return buf
