# -*- coding: utf-8 -*-
"""
    profiling.remote.select
    ~~~~~~~~~~~~~~~~~~~~~~~

    Implements a profiling server based on `select`_.

    .. _select: https://docs.python.org/library/select.html

"""
from __future__ import absolute_import
import select

from . import ProfilingServer


__all__ = ['SelectProfilingServer']


class SelectProfilingServer(ProfilingServer):

    def __init__(self, listener, *args, **kwargs):
        super(SelectProfilingServer, self).__init__(*args, **kwargs)
        self.listener = listener

    def serve_forever(self):
        while True:
            self.select()

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
        try:
            ready, __, __ = select.select(self.sockets(), (), (), timeout)
        except ValueError:
            # there's fd=0 socket.
            return
        except select.error as exc:
            if exc.args[0] == 4:
                # Interrupted system call
                return
            raise
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
