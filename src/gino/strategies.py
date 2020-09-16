import asyncio
from copy import copy

from sqlalchemy import util
from sqlalchemy.engine.url import make_url
from sqlalchemy.engine.strategies import EngineStrategy

from .engine import GinoEngine
from .dialects.asyncpg import AsyncpgDialect


class GinoStrategy(EngineStrategy):
    """A SQLAlchemy engine strategy for GINO.

    This strategy is initialized automatically as :mod:`gino` is imported.

    If :func:`sqlalchemy.create_engine` uses ``strategy="gino"``, it will return a
    :class:`~collections.abc.Coroutine`.
    """

    name = "gino"
    engine_cls = GinoEngine

    async def create(self, name_or_url, loop=None, **kwargs):
        engine_cls = self.engine_cls
        url = make_url(name_or_url)
        if loop is None:
            loop = asyncio.get_event_loop()

        # The postgresql dialect is already taken by the PGDialect_psycopg2
        # we need to force ourone.
        if url.drivername in ("postgresql", "postgres"):
            dialect_cls = AsyncpgDialect
        else:
            dialect_cls = url.get_dialect()

        pop_kwarg = kwargs.pop

        dialect_args = {}
        # consume dialect arguments from kwargs
        for k in util.get_cls_kwargs(dialect_cls).union(
            getattr(dialect_cls, "init_kwargs", set())
        ):
            if k in kwargs:
                dialect_args[k] = pop_kwarg(k)

        kwargs.pop("module", None)  # unused
        dbapi_args = {}
        for k in util.get_func_kwargs(dialect_cls.dbapi):
            if k in kwargs:
                dbapi_args[k] = pop_kwarg(k)
        dbapi = dialect_cls.dbapi(**dbapi_args)
        dialect_args["dbapi"] = dbapi

        dialect = dialect_cls(**dialect_args)
        pool_class = kwargs.pop("pool_class", None)
        pool = await dialect.init_pool(url, loop, pool_class=pool_class)

        engine_args = dict(loop=loop)
        for k in util.get_cls_kwargs(engine_cls):
            if k in kwargs:
                engine_args[k] = pop_kwarg(k)

        # all kwargs should be consumed
        if kwargs:
            raise TypeError(
                "Invalid argument(s) %s sent to create_engine(), "
                "using configuration %s/%s.  Please check that the "
                "keyword arguments are appropriate for this combination "
                "of components."
                % (
                    ",".join("'%s'" % k for k in kwargs),
                    dialect_cls.__name__,
                    engine_cls.__name__,
                )
            )

        engine = engine_cls(dialect, pool, **engine_args)

        dialect_cls.engine_created(engine)

        return engine


GinoStrategy()
