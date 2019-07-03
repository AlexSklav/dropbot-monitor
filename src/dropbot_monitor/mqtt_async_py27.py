import functools as ft
import json

from logging_helpers import _L
import json_tricks as jt
import trollius as asyncio


@asyncio.coroutine
def wait_for_result(client, verb, prefix, name, *args, **kwargs):
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
    result = asyncio.Event()

    def on_received(client, userdata, message):
        try:
            payload = message.payload or 'null'
            result.data = jt.loads(payload)
        except Exception:
            result.data = json.loads(payload)
            try:
                module_name = '.'.join(result.data['__instance_type__'][:-1])
                class_name = result.data['__instance_type__'][-1]
                module = __import__(module_name)
                cls = getattr(module, class_name)
                result.data = cls(**result.data['attributes'])
            except Exception:
                pass
        loop.call_soon_threadsafe(result.set)

    client.message_callback_add('%s/result/%s' % (prefix, name), on_received)

    try:
        payload = jt.dumps({'args': args, 'kwargs': kwargs})
        client.publish('%s/%s/%s' % (prefix, verb, name), payload=payload,
                       qos=1)
        yield asyncio.From(result.wait())
    finally:
        client.message_callback_remove(sub='%s/result/%s' % (prefix, name))
    raise asyncio.Return(result.data)


def catch_cancel(f, message=None):
    @ft.wraps(f)
    @asyncio.coroutine
    def _wrapped(*args):
        try:
            yield asyncio.From(f(*args))
        except asyncio.CancelledError:
            _L().info(message or 'Coroutine cancelled.')
    return _wrapped
