from .api import Gino  # NOQA
from .engine import GinoEngine, GinoConnection  # NOQA
from .exceptions import *  # NOQA
from .strategies import GinoStrategy  # NOQA


def create_engine(*args, **kwargs):
    from sqlalchemy import create_engine

    kwargs.setdefault("strategy", "gino")
    return create_engine(*args, **kwargs)


def get_version():
    try:
        from importlib.metadata import version
    except ImportError:
        from importlib_metadata import version
    return version("gino")


# noinspection PyBroadException
try:
    __version__ = get_version()
except Exception:
    pass
