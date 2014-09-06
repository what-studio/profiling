# -*- coding: utf-8 -*-
"""
    profiling.remote.select
    ~~~~~~~~~~~~~~~~~~~~~~~

    Implements a profiling server based on `select`_.  It recommends you how
    a profiling server works.

    Don't launch a server by multithreading.  A profiler cannot trace other
    threads.  But if you are on a `gevent`_ monkey-patched system and if you
    set a profiler using :class:`profiling.timers.greenlet.GreenletTimer` as
    timer, it will work well.

    .. _select: https://docs.python.org/library/select.html
    .. _gevent: http://gevent.org/

"""
from __future__ import absolute_import
import select
import time

from . import (INTERVAL, LOG, PICKLE_PROTOCOL, fmt_connected, fmt_disconnected,
               fmt_profiler_started, fmt_profiler_stopped, pack_stats)
from ..profiler import Profiler


__all__ = ['run_profiling_server']


def run_profiling_server(listener, profiler=None, interval=INTERVAL, log=LOG,
                         pickle_protocol=PICKLE_PROTOCOL):
    """Runs a profiling server synchronously.  Make a accept socket and call
    it::

       sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
       sock.bind(('', 0))
       sock.listen(1)
       run_profiling_server(sock, interval=10)

    This function blocks the thread.
    """
    if profiler is None:
        profiler = Profiler()
    timeout_at = None
    clients = set()
    while True:
        timeout = None if timeout_at is None else timeout_at - time.time()
        socks = clients.union([listener])
        ready, __, __ = select.select(socks, (), (), timeout)
        for sock in ready:
            if sock is listener:
                _connected(sock, clients, log, interval)
            else:
                _disconnected(sock, clients, log, profiler)
        if not clients:
            timeout_at = None
            continue
        now = time.time()
        # broadcast the statistics.
        if timeout_at is not None and timeout_at < now:
            profiler.stop()
            data = pack_stats(profiler)
            profiler.clear()
            for sock in clients:
                sock.sendall(data)
            timeout_at = None
        # start the profiler.
        if timeout_at is None:
            timeout_at = now + interval
            profiler.start()


def _connected(listener, clients, log, interval):
    sock, addr = listener.accept()
    clients.add(sock)
    num_clients = len(clients)
    log(fmt_connected(addr, num_clients))
    if num_clients == 1:
        log(fmt_profiler_started(interval))


def _disconnected(sock, clients, log, profiler):
    addr = sock.getsockname()
    clients.remove(sock)
    sock.close()
    log(fmt_disconnected(addr, len(clients)))
    if not clients and profiler.is_running():
        profiler.stop()
        log(fmt_profiler_stopped())
