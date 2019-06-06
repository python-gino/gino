from .api import Gino  # NOQA
from .engine import GinoEngine, GinoConnection  # NOQA
from .exceptions import *  # NOQA
from .strategies import GinoStrategy  # NOQA


def create_engine(*args, **kwargs):
    from sqlalchemy import create_engine

    kwargs.setdefault('strategy', 'gino')
    return create_engine(*args, **kwargs)


__version__ = '0.8.3'
