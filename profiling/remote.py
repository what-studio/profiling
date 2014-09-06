# -*- coding: utf-8 -*-
"""
    profiling.remote
    ~~~~~~~~~~~~~~~~

    Server and client implementation for remote profiling.

"""
from __future__ import absolute_import
import io
from logging import getLogger as get_logger
try:
    import cPickle as pickle
except ImportError:
    import pickle
import select
import socket
import struct
import time

from .profiler import Profiler


__all__ = ['recv_stats', 'run_server']


LOGGER = get_logger('Profiling')
SIZE_STRUCT_FORMAT = '!Q'  # unsigned long long
try:
    DEFAULT_PICKLE_PROTOCOL = pickle.DEFAULT_PROTOCOL
except AttributeError:
    DEFAULT_PICKLE_PROTOCOL = pickle.HIGHEST_PROTOCOL


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


def run_server(listener, profiler=None, interval=5, log=LOGGER.debug,
               pickle_protocol=DEFAULT_PICKLE_PROTOCOL):
    """Runs the profiler server."""
    if profiler is None:
        profiler = Profiler()
    timeout_at = None
    conns = set()
    dump = io.BytesIO()
    while True:
        timeout = None if timeout_at is None else timeout_at - time.time()
        rlist, __, __ = select.select(conns.union([listener]), (), (), timeout)
        for sock in rlist:
            if sock is listener:
                # a new connection
                _connected(sock, conns, log, interval)
            else:
                # a connection closed
                _disconnected(sock, conns, log, profiler)
        if not conns:
            timeout_at = None
            continue
        now = time.time()
        # broadcast the profile result
        if timeout_at is not None and timeout_at < now:
            profiler.stop()
            _clear(dump)
            pickle.dump(profiler.frozen_stats(), dump, pickle_protocol)
            data = _pack(dump)
            for sock in conns:
                sock.sendall(data)
            timeout_at = None
        # start the profiler
        if timeout_at is None:
            timeout_at = now + interval
            profiler.clear()
            profiler.start()


def _connected(listener, conns, log, interval):
    sock, addr = listener.accept()
    conns.add(sock)
    num_conns = len(conns)
    if addr:
        fmt = 'Connected {0[0]}:{0[1]} (total: {1})'
    else:
        fmt = 'A client connected (total: {1})'
    log(fmt.format(addr, num_conns))
    if num_conns == 1:
        log('Profiling every {0} seconds...'.format(interval))


def _disconnected(sock, conns, log, profiler):
    addr = sock.getsockname()
    conns.remove(sock)
    sock.close()
    if addr:
        fmt = 'Disconnected from {0[0]}:{0[1]} (total: {1})'
    else:
        fmt = 'A client disconnected (total: {1})'
    log(fmt.format(addr, len(conns)))
    if not conns and profiler.is_running():
        profiler.stop()
        log('Profiling disabled')


def _clear(dump):
    dump.seek(0)
    dump.truncate(0)


def _pack(dump):
    dump.seek(0, io.SEEK_END)
    length = dump.tell()
    dump.seek(0)
    return struct.pack(SIZE_STRUCT_FORMAT, length) + dump.read()
