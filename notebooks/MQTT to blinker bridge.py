# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.3'
#       jupytext_version: 1.0.2
#   kernelspec:
#     display_name: Python 2
#     language: python
#     name: python2
# ---

# %load_ext autoreload
# %autoreload 1

# +
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import logging

from dropbot import EVENT_ENABLE, EVENT_CHANNELS_UPDATED, EVENT_SHORTS_DETECTED
from paho.mqtt.client import Client
import dropbot as db
import dropbot.hardware_test
import dropbot.monitor
import pandas as pd
import trollius as asyncio
import dropbot_monitor as dbm
# %aimport dropbot_monitor
# %aimport dropbot_monitor.mqtt_bridge
# %aimport dropbot_monitor.mqtt_async_py27
# -

client = Client()
client.on_connect = dbm.mqtt_bridge.on_connect
client.connect_async('localhost')
client.loop_start()

# +
logging.basicConfig(level=logging.INFO)

monitor_task = dbm.mqtt_bridge.monitor(client)
# -

loop = asyncio.get_event_loop()
loop.run_until_complete(monitor_task.property('voltage', 80))
loop.run_until_complete(monitor_task.property('voltage'))

loop = asyncio.get_event_loop()
loop.run_until_complete(monitor_task.call('update_state',
                                          capacitance_update_interval_ms=0,
                                          hv_output_selected=True,
                                          hv_output_enabled=True,
                                          voltage=90,
                                          event_mask=EVENT_CHANNELS_UPDATED |
                                          EVENT_SHORTS_DETECTED |
                                          EVENT_ENABLE))
# loop.run_until_complete(monitor_task.call('update_state',
#                                           capacitance_update_interval_ms=500))
loop.run_until_complete(monitor_task.call('set_state_of_channels',
#                                           pd.Series(1, index=[100]),
                                          pd.Series(),
                                          append=False))
states = loop.run_until_complete(monitor_task.property('state_of_channels'))
states[states > 0]

monitor_task.stop()
