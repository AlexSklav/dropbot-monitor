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
import datetime as dt
import functools as ft
import logging
import re
import sys
import threading

from asyncio_helpers import cancellable
from dropbot import EVENT_ENABLE, EVENT_CHANNELS_UPDATED, EVENT_SHORTS_DETECTED
from dropbot_monitor import bind, unbind, wait_for_result
from dropbot_monitor.monitor import monitor
from logging_helpers import _L
from paho.mqtt.client import Client, MQTTMessage
import blinker
import blinker
import dropbot as db
import dropbot.hardware_test
import dropbot.monitor
import json_tricks as jt
import pandas as pd
import trollius as asyncio

# Prevent json_tricks Pandas dump/load warnings.
jt.encoders.pandas_encode._warned = True
jt.decoders.pandas_hook._warned = True


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
    client.subscribe('/#', qos=1)

    
cre_topic = re.compile(r'^/dropbot/(?P<uuid>[^/]+)/'
                       r'(?P<type>signal|property|call|result)/'
                       r'(?P<name>[^/]+)$')


def on_message(client, userdata, message, dropbot=None):
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
        if not message.payload:
            payload = {}
        else:
            payload = jt.loads(message.payload)
    except Exception:
        _L().debug('could not decode JSON message=`%s`', message.payload,
                   exc_info=True)
        payload = message.payload
        
    match = cre_topic.match(message.topic)
    if match:
        uuid_, type_, name = match.groups()
        print('\r%-300s' % ('%s(%s::%s)@%s: `%s`' % (type_, uuid_, name,
                                                     message.qos, payload)),
              end='')
        if dropbot is not None:
            if type_ == 'call':
                f = getattr(dropbot, name)
                try:
                    result = f(*payload.get('args', tuple()),
                               **payload.get('kwargs', {}))
                except Exception:
                    _L().error('call error: name=`%s`, payload=`%s`', name,
                               payload, exc_info=True)
                else:
                    _L().debug('call: name=`%s`, payload=`%s`', name, payload)
                    client.publish('/dropbot/%s/result/%s' % (uuid_, name),
                                   payload=jt.dumps(result))
            elif type_ == 'property':
                try:
                    args = payload.get('args', tuple(payload))
                    if not args:
                        value = getattr(dropbot, name)
                        payload = jt.dumps(value)
                    else:
                        setattr(dropbot, name, args[0])
                        payload = None
                except Exception:
                    _L().error('property error: name=`%s`', name,
                               exc_info=True)
                else:
                    _L().debug('property: name=`%s`', name)
                    client.publish('/dropbot/%s/result/%s' % (uuid_, name),
                                   payload=payload)
            elif type_ == 'set':
                try:
                    setattr(dropbot, name, value)
                except Exception:
                    _L().error('set error: name=`%s`', name, exc_info=True)
                else:
                    _L().debug('set: name=`%s`', name)
                    client.publish('/dropbot/%s/result/%s' % (uuid_, name))
    else:
        print('\r%-300s' % ('message(%s)@%s: `%s`' % (message.topic,
                                                      message.qos,
                                                      payload)),
              end='')


def monitor():
    signals = blinker.Namespace()
    
    @asyncio.coroutine
    def _on_dropbot_connected(sender, **message):
        dropbot_ = message['dropbot']
        monitor_task.dropbot = dropbot_
        client.on_message = ft.partial(on_message, dropbot=dropbot_)
        
        device_id = str(dropbot_.uuid)
        connect_topic = '/dropbot/%(uuid)s/signal' % {'uuid': device_id}
        send_topic = '/dropbot/%(uuid)s/send-signal' % {'uuid': device_id}

        bind(signals=signals, paho_client=client,
             connect_topic=connect_topic, send_topic=send_topic)
        
        dropbot_.update_state(event_mask=EVENT_CHANNELS_UPDATED |
                              EVENT_SHORTS_DETECTED | EVENT_ENABLE)
        
        client.publish('/dropbot/%(uuid)s/properties' % {'uuid': device_id},
                       payload=dropbot_.properties.to_json(), qos=1,
                       retain=True)
        
        prefix = '/dropbot/' + device_id
        monitor_task.device_id = device_id
        monitor_task.property = ft.partial(wait_for_result, client, 'property',
                                           prefix)
        monitor_task.call = ft.partial(wait_for_result, client, 'call', prefix)
        
    @asyncio.coroutine
    def _on_dropbot_disconnected(sender, **message):
        unbind(signals)
        client.publish('/dropbot/%(uuid)s/properties' %
                       {'uuid': monitor_task.device_id}, payload=None, qos=1,
                       retain=True)

    signals.signal('connected').connect(_on_dropbot_connected, weak=False)
    signals.signal('disconnected').connect(_on_dropbot_disconnected,
                                           weak=False)

    @asyncio.coroutine
    def dropbot_monitor(*args):
        try:
            yield asyncio.From(db.monitor.monitor(*args))
        except asyncio.CancelledError:
            _L().info('Stopped DropBot monitor.')
            
    def stop():
        monitor_task.dropbot.set_state_of_channels(pd.Series(), append=False)
        monitor_task.dropbot.update_state(capacitance_update_interval_ms=0,
                                          hv_output_enabled=False)
        unbind(monitor_task.signals)
        monitor_task.cancel()

    monitor_task = cancellable(dropbot_monitor)
    thread = threading.Thread(target=monitor_task, args=(signals, ))
    thread.daemon = True
    thread.start()
    monitor_task.signals = signals
    monitor_task.stop = stop
    return monitor_task



# +
logging.basicConfig(level=logging.INFO)
logging.getLogger('root').setLevel(logging.CRITICAL)

client = Client(client_id='DropBot MQTT bridge')
client.on_connect = on_connect
client.on_disconnect = ft.partial(dump, '[DISCONNECT]')
# client.on_message = ft.partial(dump, '[MESSAGE]')
client.on_message = on_message
client.connect_async('localhost')
client.loop_start()
# signal.connect(dump)
# -

monitor_task = monitor()

loop = asyncio.get_event_loop()
loop.run_until_complete(monitor_task.property('voltage', 100))

loop = asyncio.get_event_loop()
loop.run_until_complete(monitor_task.call('update_state',
                                          capacitance_update_interval_ms=0,
                                          hv_output_selected=True,
                                          hv_output_enabled=True,
                                          voltage=90,
                                          event_mask=EVENT_CHANNELS_UPDATED |
                                          EVENT_SHORTS_DETECTED |
                                          EVENT_ENABLE))
loop.run_until_complete(monitor_task.call('update_state',
                                          capacitance_update_interval_ms=500))
loop.run_until_complete(monitor_task.call('set_state_of_channels',
#                                           pd.Series(1, index=[100]),
                                          pd.Series(),
                                          append=False))

monitor_task.stop()
