from .api import Gino
from .engine import GinoEngine, GinoConnection
from .exceptions import *
from .strategies import GinoStrategy


async def create_engine(*args, **kwargs):
    import asyncio
    from sqlalchemy import create_engine

    kwargs.setdefault('strategy', 'gino')
    rv = create_engine(*args, **kwargs)
    if asyncio.iscoroutine(rv):
        # noinspection PyUnresolvedReferences
        rv = await rv
    return rv

__version__ = '0.6.1'
