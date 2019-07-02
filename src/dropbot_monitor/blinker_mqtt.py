from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import json

from logging_helpers import _L

__all__ = ['bind', 'unbind']

def bind(signals, paho_client, connect_topic='/signal',
         send_topic='/signal-send'):
    '''
    Bind a blinker signals namespace to a Paho MQTT client.

    Each blinker signal sent is forwarded to the MQTT topic
    ``<connect_topic>/<signalname>``. Each MQTT message received at the topic
    ``<send_topic>/<signalname>`` is sent to the corresponding ``<signalname>``
    blinker signal.

    Note that MQTT message payloads are encoded/decoded as JSON.


    Parameters
    ----------
    signals : blinker.Namespace
    paho_client : paho.mqtt.client.Client
    connect_topic : str
        Topic prefix to use for signals sent to ``blinker`` namespace.
    send_topic : str
        Topic prefix for MQTT subscriptions which result in sending the
        corresponding signal to the ``blinker`` namespace.
    '''
    if hasattr(signals, 'paho_client'):
        raise RuntimeError('signals already bound to client with ID: `%s`' %
                           signals.paho_client._client_id)

    # Use paho MQTT client.
    signals.paho_client = paho_client
    signals.connect_topic = connect_topic
    signals.send_topic = send_topic
    signals._most_recent_message = None
    signals._signal = signals.signal
    signals._blinker_receivers = []
    signals._mqtt_callbacks = set()

    def signal(name, doc=None):
        bind_required = (name not in signals)
        signal = signals._signal(name, doc=doc)
        if bind_required:
            bind_signal(signal, name)
        return signal

    def bind_signal(signal, name):
        def mqtt_publish(sender_name, **payload):
            # Connect callback to `signal` -> publish to MQTT `connect_topic`
            topic = '/'.join([connect_topic.rstrip('/'), name])

            try:
                payload['__sender__'] = sender_name
                message = json.dumps(payload)
                paho_client.publish(topic, payload=message)
            except Exception:
                _L().error('error publishing message; payload=`%s`, '
                           'signal=`%s`', payload, name,
                           exc_info=True)

        signal.connect(mqtt_publish, weak=False)
        signals._blinker_receivers.append((name, mqtt_publish))

        # Connect callback: MQTT subscription -> send to blinker signal
        def blinker_send(client, userdata, message):
            '''
            Parameters
            ----------

            client : paho.mqtt.client.Client
                iThe client instance for this callback
            userdata
                The private user data as set in Client() or userdata_set()
            message : paho.mqtt.client.MQTTMessage
                This is a class with members topic, payload, qos, retain.
            '''
            signals._most_recent_message = message
            try:
                payload = json.loads(message.payload)
                signal.send(paho_client._client_id, __topic__=topic, **payload)
            except Exception:
                _L().error('error sending message; payload=`%s`, '
                           'signal=`%s`', message.payload, name,
                           exc_info=True)

        topic = '/'.join([send_topic.rstrip('/'), name])
        paho_client.message_callback_add(topic, blinker_send)
        signals._mqtt_callbacks.add(topic)
        return signal

    signals.signal = signal
    for signal in signals:
        bind_signal(signals[signal], signal)
    return signals


def unbind(signals):
    '''
    Unbind a blinker signals namespace from a Paho MQTT client.

    Undo `bind()` operation.


    Parameters
    ----------
    signals : blinker.Namespace
        Signals namespace that was previously bound to a Paho MQTT client.

    '''
    if not hasattr(signals, 'paho_client'):
        raise RuntimeError('signals was not bound to a Paho MQTT client.')
    # Remove MQTT messages callback
    for sub in sorted(signals._mqtt_callbacks):
        signals.paho_client.message_callback_remove(sub)
    # Disconnect blinker callbacks
    for name, callback in signals._blinker_receivers:
        signals.signal(name).disconnect(callback)
    # Restore original `signal()` method.
    signals.signal = signals._signal
    # Remove custom attributes added by `bind()`.
    del signals._blinker_receivers
    del signals._most_recent_message
    del signals._mqtt_callbacks
    del signals._signal
    del signals.connect_topic
    del signals.paho_client
    del signals.send_topic
