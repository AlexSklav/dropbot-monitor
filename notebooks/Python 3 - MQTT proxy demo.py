# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.4'
#       jupytext_version: 1.1.7
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# +
# Workaround https://github.com/jupyter/notebook/issues/3397
import nest_asyncio
nest_asyncio.apply()

import sys
print(sys.version)

import logging

import dropbot as db
import dropbot_monitor as dbm
import dropbot_monitor.mqtt_proxy

logging.basicConfig(level=logging.INFO)
# logging.getLogger('dropbot_monitor').setLevel(logging.INFO)
# logging.getLogger('dropbot.proxy_py3.SerialProxy._send_command').setLevel(logging.INFO)
# logging.getLogger('base_node_rpc._async_py36').setLevel(logging.INFO)

# +
# Create proxy instance with **asynchronous** API.
aproxy = dbm.mqtt_proxy.MqttProxy.from_uri(db.proxy_py2.SerialProxy, 'dropbot', 'localhost',
                                           async_=True)
# Create proxy instance with **synchronous** API.
# Reuse MQTT client connection from `aproxy`.
proxy = dbm.mqtt_proxy.MqttProxy(db.proxy_py2.SerialProxy, client=aproxy.__client__,
                                 async_=False)

proxy.voltage = 100  # Using sync API
display(proxy.voltage)  # Using sync API
display(await aproxy.voltage)  # Using async API
proxy.voltage = 50  # Using sync API
display(proxy.voltage)  # Using sync API
display(await aproxy.voltage)  # Using async API
proxy.properties
# -

proxy.set

proxy.state

import pandas as pd

proxy.set_state_of_channels(pd.Series(1, index=[0]), append=False)
