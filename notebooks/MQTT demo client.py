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
import json
import logging

from paho.mqtt.client import Client, MQTTMessage
from logging_helpers import _L


def dump(message, *args, **kwargs):
    print('\r%-150s' % ('%s args: `%s` kwargs: `%s`' % (message, args, kwargs)),
          end='')
    
    
def on_message(client, userdata, message):
    '''
    Parameters
    ----------
    client : paho.mqtt.client.Client
        The client instance for this callback
    userdata
        The private user data as set in Client() or userdata_set()
    message : paho.mqtt.client.MQTTMessage
        This is a class with members topic, payload, qos, retain.
    '''
    try:
        payload = json.loads(message.payload)
        print('\r%-150s' % ('message (%s)@%s: `%s`' % (message.topic,
                                                       message.qos,
                                                       payload)),
              end='')
    except Exception:
        _L().error('Error: message=`%s`', message.payload, exc_info=True)
    

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
    dump('[CONNECT]', client, userdata, flags, rc)
    client.subscribe('/signal/#')

logging.basicConfig(level=logging.DEBUG)

client = Client(client_id='MicroDrop 1')
client.on_connect = on_connect
client.on_disconnect = ft.partial(dump, '[DISCONNECT]')
client.on_message = on_message
client.connect_async('localhost')
client.loop_start()
# -
payload = {"foobar": "hello, world!",
           "timestamp": dt.datetime.now().isoformat()}
client.publish('/signal-send/foo', payload=json.dumps(payload))
