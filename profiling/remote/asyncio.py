# -*- coding: utf-8 -*-
"""
    profiling.remote.async
    ~~~~~~~~~~~~~~~~~~~~~~

    Implements a profiling server based on `asyncio`_.  Only for Python 3.4 or
    later.

    .. _asyncio: https://docs.python.org/3/library/asyncio.html

"""
from __future__ import absolute_import
import asyncio

from . import BaseProfilingServer


__all__ = ['AsyncIOProfilingServer']


class AsyncIOProfilingServer(BaseProfilingServer):
    """A profiling server implementation based on `asyncio`_.  Launch a server
    by ``asyncio.start_server`` or ``asyncio.start_unix_server``::

       server = AsyncIOProfilingServer(interval=10)
       ready = asyncio.start_server(server)
       loop = asyncio.get_event_loop()
       loop.run_until_complete(ready)
       loop.run_forever()

    .. _asyncio: https://docs.python.org/3/library/asyncio.html

    """

    def __init__(self, *args, **kwargs):
        super(AsyncIOProfilingServer, self).__init__(*args, **kwargs)
        self.clients = set()

    def _send(self, client, data):
        reader, writer = client
        writer.write(data)

    def _close(self, client):
        reader, writer = client
        writer.close()

    def _addr(self, client):
        reader, writer = client
        return writer.get_extra_info('peername')

    def _start_profiling_loop(self):
        asyncio.async(self.profile_periodically())

    def _detect_disconnection(self, client):
        reader, writer = client
        disconnected = lambda x: self.disconnected(reader, writer)
        asyncio.async(reader.read()).add_done_callback(disconnected)

    @asyncio.coroutine
    def profile_periodically(self):
        for data in self.profiling_loop():
            if data is None:
                yield from asyncio.sleep(self.interval)
                continue
            for reader, writer in self.clients:
                writer.write(data)

    def __call__(self, reader, writer):
        client = (reader, writer)
        self.connected(client)
