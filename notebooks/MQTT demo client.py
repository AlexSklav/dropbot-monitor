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
import logging

import dropbot as db
import dropbot_monitor as dbm
import dropbot_monitor.mqtt_proxy
from dropbot_monitor import asyncio
from imp import reload
reload(dbm)
reload(dbm.mqtt_proxy)

# +
logging.basicConfig(level=logging.DEBUG)

with dbm.mqtt_proxy.MqttProxy.from_uri(db.proxy.Proxy, 'dropbot',
                                       'localhost') as proxy:
    proxy.voltage = 80
    display(proxy.voltage)
    display(proxy.measure_voltage())
    proxy.voltage = 105
    display(proxy.voltage)
    proxy.measure_voltage()


# +
@asyncio.coroutine
def demo(value):
    yield asyncio.From(aproxy
                       .update_state(capacitance_update_interval_ms=value))
    result = yield asyncio.From(aproxy.state)
    raise asyncio.Return(result)
    
    
loop = asyncio.get_event_loop()

with dbm.mqtt_proxy.MqttProxy.from_uri(db.proxy.Proxy, 'dropbot', 'localhost',
                                       async_=True) as aproxy:
    display(loop.run_until_complete(demo(500)))
    display(loop.run_until_complete(demo(0)))
