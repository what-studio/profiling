# -*- coding: utf-8 -*-
"""
    profiling.remote.errnos
    ~~~~~~~~~~~~~~~~~~~~~~~

    Socket error numbers.

"""
from __future__ import absolute_import


ENOENT = 2          # No such file.
EBADF = 9           # Bad file descriptor.
EAGAIN = 11         # Resource temporarily unavailable.
EPIPE = 32          # Broken pipe.
ECONNRESET = 54     # Connection reset by peer.
ECONNREFUSED = 111  # Connection refused.
EINPROGRESS = 115   # Operation now in progress.


__all__ = [name for name in locals().keys() if name.startswith('E')]
