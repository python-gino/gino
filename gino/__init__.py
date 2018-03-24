from .api import Gino
from .engine import GinoEngine, GinoConnection
from .exceptions import *
from .strategies import GinoStrategy


def create_engine(*args, **kwargs):
    from sqlalchemy import create_engine

    kwargs.setdefault('strategy', 'gino')
    return create_engine(*args, **kwargs)


__version__ = '0.6.2'
