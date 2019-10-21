from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import functools as ft
import inspect
import logging
import re
import threading

from dropbot_monitor import wait_for_result, asyncio
from logging_helpers import _L
from paho.mqtt.client import Client
import blinker
import json_tricks as jt

# Prevent json_tricks Pandas dump/load warnings.
jt.encoders.pandas_encode._warned = True
jt.decoders.pandas_hook._warned = True

__all__ = ['MqttProxy']

cre_topic = re.compile(r'^/[^/]+/(?P<uuid>[^/]+)/signal/'
                       r'(?P<signalname>[^/]+)$')
cre_properties = re.compile(r'^/[^/]+/(?P<uuid>[^/]+)/properties')


def on_message(name, signals, client, userdata, message):
    '''
    Parameters
    ----------
    name : str
    signals : blinker.Namespace
    client : paho.mqtt.client.Client
        The client instance for this callback
    userdata
        The private user data as set in Client() or userdata_set()
    message : paho.mqtt.client.MQTTMessage
        This is a class with members topic, payload, qos, retain.
    '''
    if not message.topic.startswith('/' + name):
        return

    match = cre_properties.match(message.topic)
    if match:
        uuid_ = match.group('uuid')
        prefix = '/%s/%s' % (name, uuid_)
        if message.payload:
            _L().debug('connect to prefix: %s', uuid_)
            client.call = ft.partial(wait_for_result, client, 'call', prefix)
            client.property = ft.partial(wait_for_result, client, 'property',
                                         prefix)
            client.connected.set()
        else:
            _L().debug('disconnect from prefix: %s', uuid_)
            client.call = None
            client.property = None
        return

    try:
        payload = jt.loads(message.payload.decode('utf-8'))
    except Exception:
        _L().debug('error decoding payload')
        payload = message.payload

    match = cre_topic.match(message.topic)
    if match:
        uuid_, signalname = match.groups()
        signals.signal(signalname).send('%s-%s' % (name, uuid_), **payload)


def on_connect(name, client, userdata, flags, rc):
    '''
    Parameters
    ----------
    name : str
    client : paho.mqtt.client.Client
        The client instance for this callback
    userdata
        The private user data as set in Client() or userdata_set()
    flags : dict
        Response flags sent by the broker
    rc : int
        The connection result
    '''
    if rc == 0:
        _L().debug('connected')
        client.subscribe('/%s/+/#' % name)


def get_client(name, signals, *args, **kwargs):
    client = Client(*args, **kwargs)
    client.connected = threading.Event()
    client.on_connect = ft.partial(on_connect, name)
    client.on_disconnect = ft.partial(lambda *args, **kwargs:
                                      logging.debug('disconnected'))
    client.on_message = ft.partial(on_message, 'dropbot', signals)
    return client


class MqttProxy(object):
    '''
    Inspect class type to extract properties and methods.

    Corresponding attributes are added to each instance, which perform the
    respective remote MQTT calls.
    '''
    def __init__(self, cls, client, async_=False):
        def wrapper(f):
            if async_:
                return f
            else:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(f)

        super(MqttProxy, self).__setattr__('async_', async_)
        super(MqttProxy, self).__setattr__('_wrapper', wrapper)
        super(MqttProxy, self).__setattr__('cls', cls)
        super(MqttProxy, self).__setattr__('__client__', client)
        super(MqttProxy, self).__setattr__('_properties',
                                           {k for k in dir(self.cls)
                                            if type(getattr(self.cls, k))
                                            is property})

        for k in dir(self.cls):
            attr = getattr(self.cls, k)
            if inspect.isfunction(attr) or inspect.ismethod(attr):
                def get_wrapped(k, attr):
                    @ft.wraps(attr)
                    def _wrapped(*args, **kwargs):
                        return self._wrapper(client.call(k, *args, **kwargs))
                    _wrapped.__doc__ = attr.__doc__
                    return _wrapped
                super(MqttProxy, self).__setattr__(k, get_wrapped(k, attr))

    @classmethod
    def from_uri(self, cls, name, host, *args, **kwargs):
        async_ = kwargs.pop('async_', False)
        signals = blinker.Namespace()
        client = get_client(name, signals, *args, **kwargs)
        client.connect_async(host)
        client.loop_start()
        client.signals = signals
        client.connected.wait()
        proxy = self(cls, client, async_=async_)
        super(MqttProxy, proxy).__setattr__('_owns_client', True)
        return proxy

    def __setattr__(self, name, value):
        if name not in self._properties:
            return super(MqttProxy, self).__setattr__(name, value)
        else:
            return self._wrapper(self.__client__.property(name, value))

    def __getattr__(self, name):
        return self._wrapper(self.__client__.property(name))

    def __dir__(self):
        return dir(self.cls)

    def __stop__(self):
        self.__client__.disconnect()
        self.__client__.loop_stop()
        _L().debug('stopped client loop')

    def __start__(self):
        self.__client__.loop_start()
        _L().debug('started client loop')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__stop__()
