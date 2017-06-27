# -*- coding: utf-8 -*-
"""
   profiling.remote.gevent
   ~~~~~~~~~~~~~~~~~~~~~~~

   Implements a profiling server based on `gevent`_.

   .. _gevent: http://gevent.org/

   :copyright: (c) 2014-2017, What! Studio
   :license: BSD, see LICENSE for more details.

"""
from __future__ import absolute_import

import socket

import gevent
from gevent.lock import Semaphore
from gevent.server import StreamServer
from gevent.util import wrap_errors

from profiling.remote import INTERVAL, LOG, PICKLE_PROTOCOL, ProfilingServer


__all__ = ['GeventProfilingServer']


class GeventProfilingServer(StreamServer, ProfilingServer):
    """A profiling server implementation based on `gevent`_.  When you choose
    it, you should set a :class:`profiling.timers.greenlet.GreenletTimer` for
    the profiler's timer::

       sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
       sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
       sock.bind(('', 0))
       sock.listen(1)

       profiler = Profiler(GreenletTimer())
       server = GeventProfilingServer(sock, profiler)
       server.serve_forever()

    .. _gevent: http://gevent.org/

    """

    def __init__(self, listener, profiler=None, interval=INTERVAL,
                 log=LOG, pickle_protocol=PICKLE_PROTOCOL, **server_kwargs):
        StreamServer.__init__(self, listener, **server_kwargs)
        ProfilingServer.__init__(self, profiler, interval,
                                 log, pickle_protocol)
        self.lock = Semaphore()

    def _send(self, sock, data):
        sock.sendall(data)

    def _close(self, sock):
        sock.close()

    def _addr(self, sock):
        return sock.getsockname()

    def _start_profiling(self):
        gevent.spawn(self.profile_periodically)

    def _start_watching(self, sock):
        disconnected = lambda x: self.disconnected(sock)
        recv = wrap_errors(socket.error, sock.recv)
        gevent.spawn(recv, 1).link(disconnected)

    def profile_periodically(self):
        with self.lock:
            for __ in self.profiling():
                gevent.sleep(self.interval)

    def handle(self, sock, addr=None):
        self.connected(sock)
