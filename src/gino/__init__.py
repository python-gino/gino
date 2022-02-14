import logging
import sys
import warnings

from .api import Gino  # NOQA
from .bakery import Bakery
from .engine import GinoEngine, GinoConnection  # NOQA
from .exceptions import *  # NOQA
from .strategies import GinoStrategy  # NOQA

rootlogger = logging.getLogger("gino")
if rootlogger.level == logging.NOTSET:
    rootlogger.setLevel(logging.WARN)


def create_engine(*args, **kwargs):
    """
    Shortcut for :func:`sqlalchemy.create_engine` with ``strategy="gino"``.
    .. versionchanged:: 1.1
       Added the ``bakery`` keyword argument, please see :class:`~.bakery.Bakery`.
    .. versionchanged:: 1.1
       Added the ``prebake`` keyword argument to choose when to create the prepared
       statements for the queries in the bakery:

       * **Pre-bake** immediately when connected to the database (default).
       * No **pre-bake** but create prepared statements lazily when needed for the first
         time.

       Note: ``prebake`` has no effect in aiomysql
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


# Check if current python version is deprecated
# Check if version is lower than 3.6
if sys.version_info < (3, 6):
    warnings.warn(
        "DEPRECATION WARNING: Python version 3.5 and lower are not supported",
        DeprecationWarning,
    )


# noinspection PyBroadException
try:
    __version__ = get_version()
except Exception:
    pass
