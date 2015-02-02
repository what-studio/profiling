# -*- coding: utf-8 -*-
"""
    profiling.remote.gevent
    ~~~~~~~~~~~~~~~~~~~~~~~

    Implements a profiling server based on `gevent`_.

    .. _gevent: http://gevent.org/

"""
from __future__ import absolute_import

import gevent
from gevent.server import StreamServer

from . import INTERVAL, LOG, PICKLE_PROTOCOL, BaseProfilingServer


__all__ = ['GeventProfilingServer']


class GeventProfilingServer(StreamServer, BaseProfilingServer):
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
        BaseProfilingServer.__init__(self, profiler, interval,
                                     log, pickle_protocol)

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
        gevent.spawn(sock.recv, 1).link(disconnected)

    def profile_periodically(self):
        for __ in self.profiling():
            gevent.sleep(self.interval)

    def handle(self, sock, addr=None):
        self.connected(sock)
