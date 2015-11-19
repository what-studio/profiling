# -*- coding: utf-8 -*-
"""
   profiling.adapting
   ~~~~~~~~~~~~~~~~~~

"""
from __future__ import absolute_import

from six import get_function_code
from valuedispatch import valuedispatch


__all__ = ['get_eventloop_ignoring_codes']


@valuedispatch
def get_eventloop_ignoring_codes(name):
    """Returns code objects the specified event-loop calls internally for
    scheduling user's tasks.
    """
    return []


@get_eventloop_ignoring_codes.register('asyncio')
def get_asyncio_ignoring_codes(__):
    import asyncio
    return map(get_function_code, [
        asyncio.BaseEventLoop.run_until_complete,
        asyncio.BaseEventLoop.run_forever, asyncio.BaseEventLoop._run_once,
        asyncio.Handle._run, asyncio.Task._wakeup, asyncio.Task._step,
    ])


@get_eventloop_ignoring_codes.register('gevent')
def get_gevent_ignoring_codes(__):
    import gevent
    import gevent.threadpool
    functions = [
        gevent.hub.Hub.run, gevent.hub.Hub.switch, gevent.hub.Waiter.switch,
        gevent.Greenlet.run, gevent.Greenlet._report_result,
        gevent.Greenlet._has_links, gevent.Greenlet._Greenlet__cancel_start,
        gevent.threadpool.ThreadPool._worker, gevent._threading.Queue.get,
        gevent._threading.Condition.wait,
    ]
    try:
        functions.append(gevent.Greenlet.kwargs.fget)
    except AttributeError:
        pass
    return map(get_function_code, functions)
