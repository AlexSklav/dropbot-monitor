from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import threading

from asyncio_helpers import cancellable
from logging_helpers import _L
import blinker
import dropbot as db
import dropbot.hardware_test
import dropbot.monitor
import trollius as asyncio


def monitor():
    signals = blinker.Namespace()

    @asyncio.coroutine
    def dropbot_monitor(*args):
        try:
            yield asyncio.From(db.monitor.monitor(*args))
        except asyncio.CancelledError:
            _L().info('Stopped DropBot monitor.')

    monitor_task = cancellable(dropbot_monitor)
    thread = threading.Thread(target=monitor_task, args=(signals, ))
    thread.daemon = True
    thread.start()
    return monitor_task
