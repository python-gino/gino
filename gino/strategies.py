from sqlalchemy import engine
from sqlalchemy.engine.strategies import DefaultEngineStrategy

from .engine import Engine


class GinoEngineStrategy(DefaultEngineStrategy):
    name = 'gino'
    engine_cls = Engine


GinoEngineStrategy()


def create_engine(*args, **kwargs):
    kwargs.setdefault('strategy', 'gino')
    return engine.create_engine(*args, **kwargs)
