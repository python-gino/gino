from .api import Gino  # NOQA
from .bakery import Bakery
from .engine import GinoEngine, GinoConnection  # NOQA
from .exceptions import *  # NOQA
from .strategies import GinoStrategy  # NOQA


def create_engine(*args, **kwargs):
    """
    Shortcut for :func:`sqlalchemy.create_engine` with ``strategy="gino"``.

    .. versionchanged:: 1.1
       Added the ``bakery`` keyword argument, please see :class:`~.bakery.Bakery`.
    """

    from sqlalchemy import create_engine

    kwargs.setdefault("strategy", "gino")
    return create_engine(*args, **kwargs)


def get_version():
    """Get current GINO version."""

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
