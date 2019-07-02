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
from __future__ import print_function
import datetime as dt
import functools as ft
import logging
import sys
# Enable `dropbot_monitor` import
sys.path.insert(0, '../src')

import blinker
from dropbot_monitor import bind, unbind
from paho.mqtt.client import Client, MQTTMessage


def dump(message, *args, **kwargs):
    print('\r%-150s' % ('%s args: `%s` kwargs: `%s`' % (message, args,
                                                        kwargs)), end='')
    

def on_connect(client, userdata, flags, rc):
    '''
    Parameters
    ==========
    client : paho.mqtt.client.Client
        The client instance for this callback
    userdata
        The private user data as set in Client() or userdata_set()
    flags : dict
        Response flags sent by the broker
    rc : int
        The connection result
    '''
    client.subscribe('/#')


# +
logging.basicConfig(level=logging.DEBUG)

client = Client(client_id='DropBot MQTT bridge')
client.on_connect = on_connect
client.on_disconnect = ft.partial(dump, '[DISCONNECT]')
client.on_message = ft.partial(dump, '[MESSAGE]')
client.connect_async('localhost')
client.loop_start()

signals = blinker.Namespace()
signal = signals.signal('foo')
# signal.connect(dump)
# -

bind(signals=signals, paho_client=client)
# unbind(signals)

signal = signals.signal('bar')
# signal.connect(dump)

payload = {"foobar": "hello, world!",
           "timestamp": dt.datetime.now().isoformat()}
# client.publish('/signal-send/foo', payload=json.dumps(payload));
client.publish('/signal/foo', payload=json.dumps(payload));

# signal.send(client._client_id, blah='hello, %s!' % dt.datetime.now().isoformat());
signals.signal('bar').send('DropBot', blah='hello, %s!' % dt.datetime.now().isoformat());
