# -*- coding: utf-8 -*-
"""
   profiling.remote.async
   ~~~~~~~~~~~~~~~~~~~~~~

   Implements a profiling server based on `asyncio`_.  Only for Python 3.4 or
   later.

   .. _asyncio: https://docs.python.org/3/library/asyncio.html

   :copyright: (c) 2014-2017, What! Studio
   :license: BSD, see LICENSE for more details.

"""
from __future__ import absolute_import

import asyncio

from profiling.remote import ProfilingServer


__all__ = ['AsyncIOProfilingServer']


class AsyncIOProfilingServer(ProfilingServer):
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

    def serve_forever(self, addr):
        host, port = addr
        loop = asyncio.get_event_loop()
        ready_to_serve = asyncio.start_server(self, host, port)
        loop.run_until_complete(ready_to_serve)
        loop.run_forever()

    def _send(self, client, data):
        reader, writer = client
        writer.write(data)

    def _close(self, client):
        reader, writer = client
        writer.close()

    def _addr(self, client):
        reader, writer = client
        return writer.get_extra_info('peername')

    def _start_profiling(self):
        asyncio.async(self.profile_periodically())

    def _start_watching(self, client):
        reader, writer = client
        disconnected = lambda x: self.disconnected(reader, writer)
        asyncio.async(reader.read()).add_done_callback(disconnected)

    @asyncio.coroutine
    def profile_periodically(self):
        for __ in self.profiling():
            yield from asyncio.sleep(self.interval)

    def __call__(self, reader, writer):
        client = (reader, writer)
        self.connected(client)
