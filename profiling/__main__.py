# -*- coding: utf-8 -*-
"""
    profiling.__main__
    ~~~~~~~~~~~~~~~~~~

    The command-line interface.

"""
from __future__ import absolute_import
from datetime import datetime
import os
try:
    import cPickle as pickle
except ImportError:
    import pickle
from stat import S_ISREG, S_ISSOCK

import click
import gevent
from gevent import socket
from urwid_geventloop import GeventLoop

from .remote import recv_stats
from .viewer import StatisticsViewer


@click.group()
def main():
    click.echo()


def parse_src(src):
    src_type = False
    try:
        mode = os.stat(src).st_mode
    except OSError:
        try:
            host, port = src.split(':')
        except ValueError:
            pass
        else:
            src_type = 'tcp'
            port = int(port)
            src = (host, port)
    else:
        if S_ISSOCK(mode):
            src_type = 'sock'
        elif S_ISREG(mode):
            src_type = 'dump'
    if not src_type:
        raise ValueError('A dump file or a socket address required.')
    return src_type, src


def run_client(viewer, address, *socket_options):
    while True:
        sock = socket.socket(*socket_options)
        try:
            sock.connect(address)
        except socket.error:
            viewer.inactivate()
            gevent.sleep(1)
            # try to reconnect
            continue
        while not sock.closed:
            try:
                with gevent.Timeout(60):
                    stats = recv_stats(sock)
            except (gevent.Timeout, socket.error):
                sock.close()
                # try to reconnect quickly
                break
            src_time = datetime.now()
            viewer.set_stats(stats, address, src_time)


@main.command()
@click.argument('src', metavar='SOURCE')
def view(src):
    try:
        src_type, src = parse_src(src)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint='src')
    viewer = StatisticsViewer()
    viewer.use_vim_command_map()
    if src_type == 'tcp':
        gevent.spawn(run_client, viewer, src)
    elif src_type == 'sock':
        gevent.spawn(run_client, viewer, src, socket.AF_UNIX)
    elif src_type == 'dump':
        with open(src) as f:
            stats = pickle.load(f)
        src_time = datetime.fromtimestamp(os.path.getmtime(src))
        viewer.set_stats(stats, src, src_time)
    loop = viewer.loop(event_loop=GeventLoop())
    loop.run()
    '''
    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    '''


if __name__ == '__main__':
    main()
