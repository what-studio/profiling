# -*- coding: utf-8 -*-
"""
    profiling.remote.client
    ~~~~~~~~~~~~~~~~~~~~~~~

"""
from __future__ import absolute_import
from datetime import datetime
import socket

from valuedispatch import valuedispatch

from . import PROFILER, STATS, WELCOME, recv_msg
from .errnos import ENOENT, ECONNREFUSED, EINPROGRESS


__all__ = ['ProfilingClient', 'FailoverProfilingClient']


@valuedispatch
def protocol(method, msg, client):
    pass


@protocol.register(WELCOME)
def handle_welcome(*_):
    pass


@protocol.register(PROFILER)
def handle_profiler(_, profiler_class, client):
    client.viewer.set_profiler_class(profiler_class)


@protocol.register(STATS)
def handle_stats(_, stats, client):
    client.viewer.set_stats(stats, client.title, datetime.now())


class ProfilingClient(object):
    """A client of profiling server which is running behind the `Urwid`_ event
    loop.

    .. _Urwid: http://urwid.org/

    """

    def __init__(self, viewer, event_loop, sock,
                 title=None, protocol=protocol):
        self.viewer = viewer
        self.event_loop = event_loop
        self.sock = sock
        self.title = title
        self.protocol = protocol

    def start(self):
        self.viewer.activate()
        self.event_loop.watch_file(self.sock.fileno(), self.handle)

    def handle(self):
        self.viewer.activate()
        try:
            method, msg = recv_msg(self.sock)
        except socket.error as exc:
            self.erred(exc.errno)
            return
        self.protocol(method, msg, self)

    def erred(self, errno):
        self.viewer.inactivate()


class FailoverProfilingClient(ProfilingClient):
    """A profiling client but it tries to reconnect constantly."""

    failover_interval = 1

    def __init__(self, viewer, event_loop, addr=None, family=socket.AF_INET,
                 title=None, protocol=protocol):
        self.addr = addr
        self.family = family
        base = super(FailoverProfilingClient, self)
        base.__init__(viewer, event_loop, None, title, protocol)

    def connect(self):
        while True:
            errno = self.sock.connect_ex(self.addr)
            if errno == 0:
                break
        if not errno:
            # connected immediately.
            pass
        elif errno == EINPROGRESS:
            # will be connected.
            pass
        elif errno == ENOENT:
            # no such socket file.
            self.create_connection(self.failover_interval)
            return
        else:
            raise ValueError('Unexpected socket errno: %d' % errno)
        self.event_loop.watch_file(self.sock.fileno(), self.handle)

    def disconnect(self, errno):
        self.event_loop.remove_watch_file(self.sock.fileno())
        self.sock.close()
        # try to reconnect.
        delay = self.failover_interval if errno == ECONNREFUSED else 0
        self.create_connection(delay)

    def create_connection(self, delay=0):
        self.sock = socket.socket(self.family)
        self.sock.setblocking(0)
        self.event_loop.alarm(delay, self.connect)

    def start(self):
        self.create_connection()

    def erred(self, errno):
        super(FailoverProfilingClient, self).erred(errno)
        self.disconnect(errno)
