# -*- coding: utf-8 -*-

"""Top-level package for GINO."""

__author__ = """Fantix King"""
__email__ = 'fantix.king@gmail.com'
__version__ = '0.3.0'

from .declarative import Gino
from .asyncpg_delegate import GinoConnection
from .local import get_local, enable_task_local, disable_task_local
