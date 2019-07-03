from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import functools as ft
import re
import threading

from asyncio_helpers import cancellable
from dropbot import EVENT_ENABLE, EVENT_CHANNELS_UPDATED, EVENT_SHORTS_DETECTED
from dropbot_monitor import bind, unbind, wait_for_result, catch_cancel
from logging_helpers import _L
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


cre_topic = re.compile(r'^/(?P<device_name>[^/]+)/(?P<uuid>[^/]+)/'
                       r'(?P<type>signal|property|call|result)/'
                       r'(?P<name>[^/]+)$')


def on_message(device_name, client, userdata, message, proxy=None):
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
    logger = _L()
    try:
        if not message.payload:
            payload = {}
        else:
            payload = jt.loads(message.payload)
    except Exception:
        logger.debug('could not decode JSON message=`%s`', message.payload,
                     exc_info=True)
        payload = message.payload

    match = cre_topic.match(message.topic)
    if match and match.group('device_name') == device_name:
        device_name, uuid_, type_, name = match.groups()
        logger.debug('%s(%s::%s)@%s: `%s`', type_, uuid_, name, message.qos,
                     payload)
        if proxy is not None:
            if type_ == 'call':
                f = getattr(proxy, name)
                try:
                    result = f(*payload.get('args', tuple()),
                               **payload.get('kwargs', {}))
                except Exception:
                    _L().error('call error: name=`%s`, payload=`%s`', name,
                               payload, exc_info=True)
                else:
                    _L().debug('call: name=`%s`, payload=`%s`', name, payload)
                    client.publish('/%s/%s/result/%s' % (device_name, uuid_,
                                                         name),
                                   payload=jt.dumps(result))
            elif type_ == 'property':
                try:
                    args = payload.get('args', tuple(payload))
                    if not args:
                        value = getattr(proxy, name)
                        payload = jt.dumps(value)
                    else:
                        setattr(proxy, name, args[0])
                        payload = None
                except Exception:
                    _L().error('property error: name=`%s`', name,
                               exc_info=True)
                else:
                    _L().debug('property: name=`%s`', name)
                    client.publish('/%s/%s/result/%s' % (device_name, uuid_,
                                                         name),
                                   payload=payload)
    else:
        logger.debug('message(%s)@%s: `%s`', message.topic, message.qos,
                     payload)


def monitor(client):
    signals = blinker.Namespace()

    @asyncio.coroutine
    def _on_dropbot_connected(sender, **message):
        dropbot_ = message['dropbot']
        monitor_task.dropbot = dropbot_
        client.on_message = ft.partial(on_message, 'dropbot', proxy=dropbot_)

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

    def stop():
        monitor_task.dropbot.set_state_of_channels(pd.Series(), append=False)
        monitor_task.dropbot.update_state(capacitance_update_interval_ms=0,
                                          hv_output_enabled=False)
        unbind(monitor_task.signals)
        monitor_task.cancel()

    monitor_task = cancellable(catch_cancel(db.monitor.monitor))
    thread = threading.Thread(target=monitor_task, args=(signals, ))
    thread.daemon = True
    thread.start()
    monitor_task.signals = signals
    monitor_task.stop = stop
    return monitor_task
