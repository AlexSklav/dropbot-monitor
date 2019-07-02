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
from logging_helpers import _L
import blinker


class MqttNamespace(blinker.Namespace):
    def __init__(self, paho_client, connect_topic='/signal',
                 send_topic='/signal-send'):
        # Use paho MQTT client.
        self.paho_client = paho_client
        self.connect_topic = connect_topic
        self.send_topic = send_topic
        self._most_recent_message = None
        
    def signal(self, name, doc=None):
        """Return the :class:`NamedSignal` *name*, creating it if required.

        Repeated calls to this function will return the same signal object.

        """
        if name in self:
            return self[name]
        else:
            signal = self.setdefault(name, blinker.NamedSignal(name, doc))    
            
            # Connect callback to `signal` -> publish to MQTT `connect_topic`
            topic = '/'.join([self.connect_topic.rstrip('/'), name])
            
            def mqtt_publish(sender_name, **payload):
                if sender_name == self.paho_client._client_id:
                    return
                try:
                    payload['__sender__'] = sender_name
                    message = json.dumps(payload)
                    self.paho_client.publish(topic, payload=message)
                except Exception:
                    _L().error('error publishing message; payload=`%s`, '
                               'signal=`%s`', payload, name,
                               exc_info=True)
                    
            signal.connect(mqtt_publish, weak=False)
                
            # Connect callback to MQTT subscription -> publish to MQTT `send_topic`
            def blinker_send(client, userdata, message):
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
                self._most_recent_message = message
                try:
                    payload = json.loads(message.payload)
                    if payload.get('__sender__') != self.paho_client\
                            ._client_id:
                        signal.send(self.paho_client._client_id,
                                    __topic__=topic, **payload)
                except Exception:
                    _L().error('error sending message; payload=`%s`, '
                               'signal=`%s`', message.payload, name,
                               exc_info=True)
                
            topic = '/'.join([self.send_topic.rstrip('/'), name])
            self.paho_client.message_callback_add(topic, blinker_send)
            return signal


# +
from __future__ import print_function
import functools as ft

from paho.mqtt.client import Client, MQTTMessage


def dump(message, *args, **kwargs):
    print(message, 'args:', args, 'kwargs:', kwargs)
    

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
import datetime as dt
import logging

logging.basicConfig(level=logging.DEBUG)

client = Client(client_id='DropBot MQTT bridge')
client.on_connect = on_connect
client.on_disconnect = ft.partial(dump, '[DISCONNECT]')
client.on_message = ft.partial(dump, '[MESSAGE]')
client.connect_async('localhost')
client.loop_start()

signals = MqttNamespace(paho_client=client)
signal = signals.signal('foo')
signal.connect(dump)
# -

client.publish('/signal-send/foo', payload='{"foobar": "hello, world!"}')

# signal.send(client._client_id, blah='hello, %s!' % dt.datetime.now().isoformat());
signal.send('DropBot', blah='hello, %s!' % dt.datetime.now().isoformat());
