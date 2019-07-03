import sys

if sys.version_info[0] < 3:
    from .mqtt_async_py27 import *
    import trollius as asyncio
else:
    from .mqtt_async_py3 import *
    import asyncio


__all__ = ['wait_for_result', 'catch_cancel', 'asyncio']
