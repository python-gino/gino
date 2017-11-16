import asyncio
from sqlalchemy import engine
from sqlalchemy.dialects import registry
from sqlalchemy.engine.strategies import DefaultEngineStrategy

from .engine import Engine


class GinoEngineStrategy(DefaultEngineStrategy):
    name = 'gino'
    engine_cls = Engine


GinoEngineStrategy()


class TaskLocalEngineStrategy(DefaultEngineStrategy):
    name = 'tasklocal'
    engine_cls = Engine


TaskLocalEngineStrategy()


def create_engine(*args, **kwargs):
    registry.register('postgresql', 'gino.dialects.asyncpg', 'AsyncpgDialect')
    try:
        kwargs.setdefault('strategy', 'gino')
        if 'loop' not in kwargs:
            kwargs['loop'] = asyncio.get_event_loop()
        return engine.create_engine(*args, **kwargs)
    finally:
        registry.auto_fn('postgresql')
