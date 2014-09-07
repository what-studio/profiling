# -*- coding: utf-8 -*-
"""
    profiling.remote.select
    ~~~~~~~~~~~~~~~~~~~~~~~

    Implements a profiling server based on `select`_.  It recommends you how
    a profiling server works.

    .. warning::

       If you want to launch a profiling server on a background thread, use
       :func:`profiling.remote.background.start_profiling_server` instead.  By
       default, a profiler cannot trace another thread already running.

    .. _select: https://docs.python.org/library/select.html

"""
from __future__ import absolute_import
import select
import time

from . import (INTERVAL, LOG, PICKLE_PROTOCOL, fmt_connected, fmt_disconnected,
               fmt_profiler_started, fmt_profiler_stopped, pack_stats)
from ..profiler import Profiler


__all__ = ['profiling_server', 'profile_and_broadcast']


def profiling_server(listener, profiler=None, interval=INTERVAL, log=LOG,
                     pickle_protocol=PICKLE_PROTOCOL):
    """Runs a profiling server synchronously.  Make a accept socket and call
    it::

       sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
       sock.bind(('', 0))
       sock.listen(1)
       profiling_server(sock, interval=10)

    This function blocks the thread.
    """
    if profiler is None:
        profiler = Profiler()
    clients = set()
    profiling = profile_and_broadcast(
        clients, profiler, interval, pickle_protocol)
    while True:
        data, timeout_at = next(profiling)
        timeout = None if timeout_at is None else timeout_at - time.time()
        socks = clients.union([listener])
        ready, __, __ = select.select(socks, (), (), timeout)
        for sock in ready:
            if sock is listener:
                sock, addr = _connected(sock, clients, log, interval)
                if data is not None:
                    sock.sendall(data)
            else:
                _disconnected(sock, clients, log, profiler)


def profile_and_broadcast(clients, profiler=None, interval=INTERVAL,
                          pickle_protocol=PICKLE_PROTOCOL):
    """A generator which starts profiling periodically then broadcasts the
    result to all clients.  Each iteration yields a tuple of the latest data
    and the time to time out.
    """
    if profiler is None:
        profiler = Profiler()
    data = None
    timeout_at = None
    while True:
        if clients:
            now = time.time()
            # broadcast the statistics.
            if timeout_at is not None and timeout_at < now:
                profiler.stop()
                data = pack_stats(profiler, pickle_protocol)
                profiler.clear()
                for sock in clients:
                    sock.sendall(data)
                timeout_at = None
            # start the profiler.
            if timeout_at is None:
                timeout_at = now + interval
                profiler.start()
        else:
            timeout_at = None
        yield data, timeout_at


def _connected(listener, clients, log, interval):
    sock, addr = listener.accept()
    clients.add(sock)
    num_clients = len(clients)
    log(fmt_connected(addr, num_clients))
    if num_clients == 1:
        log(fmt_profiler_started(interval))
    return sock, addr


def _disconnected(sock, clients, log, profiler):
    addr = sock.getsockname()
    clients.remove(sock)
    sock.close()
    log(fmt_disconnected(addr, len(clients)))
    if not clients and profiler.is_running():
        profiler.stop()
        log(fmt_profiler_stopped())
