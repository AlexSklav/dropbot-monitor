import json

from logging_helpers import _L
import json_tricks as jt
import asyncio


async def wait_for_result(client, verb, prefix, name, *args, **kwargs):
    '''
    Example
    -------

    >>> client = Client(client_id='DropBot MQTT bridge')
    >>> ...
    >>> # bind MQTT client to DropBot monitor blinker signals namespace...
    >>> ...
    >>> prefix = '/dropbot/' + str(dropbot.uuid)
    >>> call = ft.partial(wait_for_result, client, 'call', prefix)
    >>> property = ft.partial(wait_for_result, client, 'property', prefix)
    >>> ...
    >>> loop = asyncio.get_event_loop()
    >>> loop.run_until_complete(property('voltage', 80))
    '''
    loop = asyncio.get_event_loop()
    _L().debug(str(loop))

    result = asyncio.Event()

    def on_received(client, userdata, message):
        try:
            payload = message.payload.decode('utf-8') or 'null'
            result.data = jt.loads(payload)
        except Exception:
            _L().debug('json_tricks loads error: `%s`', payload, exc_info=True)
            result.data = json.loads(payload)
            try:
                module_name = '.'.join(result.data['__instance_type__'][:-1])
                class_name = result.data['__instance_type__'][-1]
                module = __import__(module_name)
                cls = getattr(module, class_name)
                result.data = cls(**result.data['attributes'])
            except Exception:
                _L().debug('json_tricks workaround failed', exc_info=True)
                pass
        loop.call_soon_threadsafe(result.set)

    logger = _L()
    topic = '%s/result/%s' % (prefix, name)
    client.message_callback_add(topic, on_received)
    logger.debug('attached callback to topic: `%s`', topic)

    try:
        payload = jt.dumps({'args': args, 'kwargs': kwargs})
        client.publish('%s/%s/%s' % (prefix, verb, name), payload=payload,
                       qos=1)
        logger.debug('wait for response')
        await result.wait()
    finally:
        client.message_callback_remove(sub=topic)
        logger.debug('detached callback from topic: `%s`', topic)
    return result.data
