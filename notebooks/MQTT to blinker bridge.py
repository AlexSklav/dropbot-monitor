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

# +
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from contextlib import closing
import logging

from base_node_rpc.async import asyncio
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError: 
    pass
from dropbot import EVENT_ENABLE, EVENT_CHANNELS_UPDATED, EVENT_SHORTS_DETECTED
import pandas as pd
import dropbot_monitor as dbm

# +
logging.basicConfig(level=logging.DEBUG)
# logging.getLogger('dropbot.proxy_py3.SerialProxy._send_command').setLevel(logging.INFO)
# logging.getLogger('base_node_rpc._async_py36').setLevel(logging.INFO)

# with closing(dbm.monitor()) as monitor_task:
monitor_task = dbm.monitor()
display(monitor_task.signals)
monitor_task.connected.wait()

loop = asyncio.get_event_loop()
loop.run_until_complete(monitor_task.property('voltage', 80))
display(loop.run_until_complete(monitor_task.property('voltage')))

loop = asyncio.get_event_loop()
loop.run_until_complete(monitor_task.call('update_state',
                                          capacitance_update_interval_ms=0,
                                          hv_output_selected=True,
                                          hv_output_enabled=True,
                                          voltage=90,
                                          event_mask=EVENT_CHANNELS_UPDATED |
                                          EVENT_SHORTS_DETECTED |
                                          EVENT_ENABLE))
# loop.run_until_complete(monitor_task.call('set_state_of_channels',
# #                                           pd.Series(1, index=[100]),
#                                           pd.Series(),
#                                           append=False))
# states = loop.run_until_complete(monitor_task.property('state_of_channels'))
# display(states[states > 0])
# -

# monitor_task.dropbot.set_state_of_channels?
loop.run_until_complete(monitor_task.call('update_state',
                                          capacitance_update_interval_ms=0,
                                          hv_output_selected=True,
                                          hv_output_enabled=True,
                                          voltage=90,
                                          event_mask=EVENT_CHANNELS_UPDATED |
                                          EVENT_SHORTS_DETECTED |
                                          EVENT_ENABLE))

#  - base-node-rpc (dropbot.py/.dropbot-recipes/_source/base-node-rpc)
#  - debounce
#  - dropbot.py

import numpy as np

np.frombuffer(b'hello', dtype='uint8')

monitor_task.dropbot.set_state_of_channels(pd.Series(), append=False)

import dropbot as db
import dropbot.node

db.node.Proxy??

loop.run_until_complete(monitor_task.call('set_state_of_channels',
                                          pd.Series(),
                                          append=False))

loop = asyncio.get_event_loop()
states = loop.run_until_complete(monitor_task.property('state_of_channels'))
display(states[states > 0])


