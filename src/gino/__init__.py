from .api import Gino  # NOQA
from .bakery import Bakery
from .exceptions import *  # NOQA
from .engine import GinoEngine, GinoConnection, create_engine  # NOQA


def get_version():
    """Get current GINO version."""

    try:
        from importlib_metadata import version
    except ImportError:
        from importlib.metadata import version
    return version("gino")


# noinspection PyBroadException
try:
    __version__ = get_version()
except Exception:
    pass
