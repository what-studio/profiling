# -*- coding: utf-8 -*-
"""
    profiling.remote.select2
    ~~~~~~~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import
import select

from . import INTERVAL, LOG, PICKLE_PROTOCOL, BaseProfilingServer


class SelectProfilingServer(BaseProfilingServer):

    def __init__(self, listener, profiler=None, log=LOG,
                 interval=INTERVAL, pickle_protocol=PICKLE_PROTOCOL):
        base = super(SelectProfilingServer, self)
        base.__init__(profiler, log, interval, pickle_protocol)
        self.listener = listener

    def _send(self, sock, data):
        sock.sendall(data)

    def _close(self, sock):
        sock.close()

    def _addr(self, sock):
        return sock.getsockname()

    def _start_profiling(self):
        self.profile_periodically()

    def _start_watching(self, sock):
        pass

    def sockets(self):
        if self.listener is None:
            return self.clients
        else:
            return self.clients.union([self.listener])

    def select(self, timeout=None):
        ready, __, __ = select.select(self.sockets(), (), (), timeout)
        for sock in ready:
            if sock is self.listener:
                listener = sock
                sock, addr = listener.accept()
                self.connected(sock)
            else:
                sock.recv(1)
                self.disconnected(sock)

    def profile_periodically(self):
        for __ in self.profiling():
            self.select(self.interval)
