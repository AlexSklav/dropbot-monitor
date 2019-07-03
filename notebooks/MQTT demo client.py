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
import re

from dropbot import EVENT_ENABLE, EVENT_CHANNELS_UPDATED, EVENT_SHORTS_DETECTED
from dropbot_monitor import bind, unbind, wait_for_result
from paho.mqtt.client import Client, MQTTMessage
from logging_helpers import _L
import blinker
import json_tricks as jt

# Prevent json_tricks Pandas dump/load warnings.
jt.encoders.pandas_encode._warned = True
jt.decoders.pandas_hook._warned = True
    
    
cre_topic = re.compile(r'^/dropbot/(?P<uuid>[^/]+)/signal/'
                       r'(?P<signalname>[^/]+)$')
cre_properties = re.compile(r'^/dropbot/(?P<uuid>[^/]+)/properties')


def dump(message, *args, **kwargs):
    print('\r%-150s' % ('%s args: `%s` kwargs: `%s`' % (message, args,
                                                        kwargs)), end='')


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
    match = cre_properties.match(message.topic)
    if match:
        uuid_ = match.group('uuid')
        prefix = '/dropbot/' + uuid_
        if message.payload:
            print('connect to prefix: %s' % uuid_)
            client.call = ft.partial(wait_for_result, client, 'call', prefix)
            client.property = ft.partial(wait_for_result, client, 'property',
                                         prefix)
        else:
            print('disconnect from prefix: %s' % uuid_)
            client.get = None
            client.call = None
            client.set_ = None
        return
    
    try:
        payload = jt.loads(message.payload)
    except Exception:
        payload = message.payload
        
    match = cre_topic.match(message.topic)
    if match:
        uuid_, signalname = match.groups()
        signals.signal(signalname).send('dropbot-%s' % uuid_, **payload)
    

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
    client.subscribe('/dropbot/+/#')

logging.basicConfig(level=logging.DEBUG)

signals = blinker.Namespace()

client = Client(client_id='MicroDrop 1')
client.on_connect = on_connect
client.on_disconnect = ft.partial(dump, '[DISCONNECT]')
client.on_message = on_message
client.connect_async('localhost')
client.loop_start()
# + {}
import inspect

import dropbot as db
import trollius as asyncio

    
class MqttProxy(object):
    '''
    Inspect class type to extract properties and methods.
    
    Corresponding attributes are added to each instance, which perform the
    respective remote MQTT calls.
    '''
    def __init__(self, cls, client, async_=False):
        loop = asyncio.get_event_loop()
        super(MqttProxy, self).__setattr__('_wrapper', loop.run_until_complete
                                           if not async_ else (lambda f: f))
        super(MqttProxy, self).__setattr__('cls', cls)
        super(MqttProxy, self).__setattr__('__client__', client)
        super(MqttProxy, self).__setattr__('_properties',
                                           {k for k in dir(self.cls)
                                            if type(getattr(self.cls, k)) 
                                            is property})
        
        for k in dir(self.cls):
            attr = getattr(self.cls, k)
            if inspect.ismethod(attr):
                def get_wrapped(k, attr):
                    @ft.wraps(attr)
                    def _wrapped(*args, **kwargs):
                        loop = asyncio.get_event_loop()
                        return self._wrapper(client.call(k, *args, **kwargs))
                    _wrapped.__doc__ = attr.__doc__
                    return _wrapped
                super(MqttProxy, self).__setattr__(k, get_wrapped(k, attr))
        
    def __setattr__(self, name, value):
        if name not in self._properties:
            return super(MqttProxy, self).__setattr__(name, value)
        else:
            return self._wrapper(self.__client__.property(name, value))
    
    def __getattr__(self, name):
        attr = getattr(self.cls, name)
        if type(attr) is property:
            return self._wrapper(self.__client__.property(name))
        else:
            return super(MqttProxy, self).__getattr__(name)
        
    def __dir__(self):
        return dir(self.cls)


# +
proxy = MqttProxy(db.proxy_py2.SerialProxy, client, async_=False)

proxy.voltage = 80
display(proxy.voltage)
display(proxy.measure_voltage())
proxy.voltage = 105
display(proxy.voltage)
proxy.measure_voltage()
# -

aproxy = MqttProxy(db.proxy.Proxy, client, async_=True)

loop = asyncio.get_event_loop()


# +
@asyncio.coroutine
def demo(value):
    yield asyncio.From(aproxy
                       .update_state(capacitance_update_interval_ms=value))
    result = yield asyncio.From(aproxy.state)
    raise asyncio.Return(result)

display(loop.run_until_complete(demo(500)))
display(loop.run_until_complete(demo(0)))
# -

client.loop_stop()
