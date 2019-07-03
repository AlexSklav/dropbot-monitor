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
    >>> get = ft.partial(wait_for_result, client, 'get', prefix)
    >>> call = ft.partial(wait_for_result, client, 'call', prefix)
    >>> set_ = ft.partial(wait_for_result, client, 'set', prefix)
    >>> ...
    >>> loop = asyncio.get_event_loop()
    >>> loop.run_until_complete(set_('voltage', 80))
    '''
    loop = asyncio.get_event_loop()

    result = asyncio.Event()

    def on_done(client, userdata, message):
        result.data = jt.loads(message.payload or 'null')
        loop.call_soon_threadsafe(result.set)

    client.message_callback_add('%s/result/%s' % (prefix, name), on_done)

    try:
        payload = jt.dumps({'args': args, 'kwargs': kwargs})
        client.publish('%s/%s/%s' % (prefix, verb, name), payload=payload,
                       qos=1)
        yield asyncio.From(result.wait())
    finally:
        client.message_callback_remove(sub='%s/result/%s' % (prefix, name))
    raise asyncio.Return(result.data)
