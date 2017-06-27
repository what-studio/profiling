# -*- coding: utf-8 -*-
"""
   profiling.remote.select
   ~~~~~~~~~~~~~~~~~~~~~~~

   Implements a profiling server based on `select`_.

   .. _select: https://docs.python.org/library/select.html

   :copyright: (c) 2014-2017, What! Studio
   :license: BSD, see LICENSE for more details.

"""
from __future__ import absolute_import

from errno import ECONNRESET, EINTR, ENOTCONN
import select
import socket
import time

from profiling.remote import ProfilingServer


__all__ = ['SelectProfilingServer']


class SelectProfilingServer(ProfilingServer):

    def __init__(self, listener, *args, **kwargs):
        super(SelectProfilingServer, self).__init__(*args, **kwargs)
        self.listener = listener

    def serve_forever(self):
        while True:
            self.dispatch_sockets()

    def _send(self, sock, data):
        sock.sendall(data, socket.MSG_DONTWAIT)

    def _close(self, sock):
        sock.close()

    def _addr(self, sock):
        try:
            return sock.getpeername()
        except socket.error as exc:
            if exc.errno == ENOTCONN:
                return None
            else:
                raise

    def _start_profiling(self):
        self.profile_periodically()

    def profile_periodically(self):
        for __ in self.profiling():
            self.dispatch_sockets(self.interval)

    def _start_watching(self, sock):
        pass

    def sockets(self):
        """Returns the set of the sockets."""
        if self.listener is None:
            return self.clients
        else:
            return self.clients.union([self.listener])

    def select_sockets(self, timeout=None):
        """EINTR safe version of `select`.  It focuses on just incoming
        sockets.
        """
        if timeout is not None:
            t = time.time()
        while True:
            try:
                ready, __, __ = select.select(self.sockets(), (), (), timeout)
            except ValueError:
                # there's fd=0 socket.
                pass
            except select.error as exc:
                # ignore an interrupted system call.
                if exc.args[0] != EINTR:
                    raise
            else:
                # succeeded.
                return ready
            # retry.
            if timeout is None:
                continue
            # decrease timeout.
            t2 = time.time()
            timeout -= t2 - t
            t = t2
            if timeout <= 0:
                # timed out.
                return []

    def dispatch_sockets(self, timeout=None):
        """Dispatches incoming sockets."""
        for sock in self.select_sockets(timeout=timeout):
            if sock is self.listener:
                listener = sock
                sock, addr = listener.accept()
                self.connected(sock)
            else:
                try:
                    sock.recv(1)
                except socket.error as exc:
                    if exc.errno != ECONNRESET:
                        raise
                self.disconnected(sock)
