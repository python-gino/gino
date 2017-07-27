import asyncio

from asyncpg.pool import Pool
from asyncpg.connection import Connection


class GinoPool(Pool):
    def __init__(self, metadata, *connect_args, min_size, max_size,
                 max_queries, max_inactive_connection_lifetime, setup, init,
                 loop, connection_class, **connect_kwargs):
        self.metadata = metadata
        super().__init__(
            *connect_args, min_size=min_size, max_size=max_size,
            max_queries=max_queries,
            max_inactive_connection_lifetime=max_inactive_connection_lifetime,
            setup=setup, init=init, loop=loop,
            connection_class=connection_class, **connect_kwargs)

    async def _async__init__(self):
        rv = await super()._async__init__()
        self.metadata.bind = self
        return rv

    async def close(self):
        self.metadata.bind = None
        self.metadata = None
        return await super().close()

    async def all(self, clause, *multiparams, **params):
        return await self.metadata.all(clause, *multiparams, **params,
                                       bind=self)

    async def first(self, clause, *multiparams, **params):
        return await self.metadata.first(clause, *multiparams, **params,
                                         bind=self)

    async def scalar(self, clause, *multiparams, **params):
        return await self.metadata.scalar(clause, *multiparams, **params,
                                          bind=self)


class GinoConnection(Connection):
    metadata = None

    async def all(self, clause, *multiparams, **params):
        return await self.metadata.all(clause, *multiparams, **params,
                                       bind=self)

    async def first(self, clause, *multiparams, **params):
        return await self.metadata.first(clause, *multiparams, **params,
                                         bind=self)

    async def scalar(self, clause, *multiparams, **params):
        return await self.metadata.scalar(clause, *multiparams, **params,
                                          bind=self)

    def iterate(self, clause, *multiparams, **params):
        return self.metadata.iterate(clause, *multiparams, **params,
                                     connection=self)


class GinoAcquireContext:
    def __init__(self, bind, timeout):
        self._bind = bind
        self._timeout = timeout
        self._ctx = None

    async def __aenter__(self):
        if hasattr(self._bind, 'acquire'):
            self._ctx = self._bind.acquire(timeout=self._timeout)
            self._bind = None
            return await self._ctx.__aenter__()
        else:
            return self._bind

    async def __aexit__(self, *exc):
        self._bind = None
        if self._ctx is not None:
            await self._ctx.__aexit__(*exc)

    def __await__(self):
        if hasattr(self._bind, 'acquire'):
            return self._bind.acquire(timeout=self._timeout).__await__()
        else:
            rv = asyncio.Future()
            rv.set_result(self._bind)
            return rv


class GinoTransaction:
    def __init__(self, gino, isolation, readonly, deferrable):
        self._gino = gino
        self._isolation = isolation
        self._readonly = readonly
        self._deferrable = deferrable
        self._conn = None
        self._ctx = None

    async def __aenter__(self):
        self._conn = await self._gino.acquire()
        self._ctx = self._conn.transaction(isolation=self._isolation,
                                           readonly=self._readonly,
                                           deferrable=self._deferrable)
        return self._conn, await self._ctx.__aenter__()

    async def __aexit__(self, extype, ex, tb):
        try:
            await self._ctx.__aexit__(extype, ex, tb)
        finally:
            conn, self._conn = self._conn, None
            await self._gino.release(conn)


class AsyncpgMixin:
    def create_pool(self, dsn=None, *,
                    min_size=10,
                    max_size=10,
                    max_queries=50000,
                    max_inactive_connection_lifetime=300.0,
                    setup=None,
                    init=None,
                    loop=None,
                    connection_class=GinoConnection,
                    **connect_kwargs):
        if not issubclass(connection_class, GinoConnection):
            raise TypeError(
                'connection_class is expected to be a subclass of '
                'gino.GinoConnection, got {!r}'.format(connection_class))

        connection_class = type(connection_class.__name__, (connection_class,),
                                {'metadata': self})
        # noinspection PyAttributeOutsideInit
        pool = GinoPool(
            self, dsn,
            connection_class=connection_class,
            min_size=min_size, max_size=max_size,
            max_queries=max_queries, loop=loop, setup=setup, init=init,
            max_inactive_connection_lifetime=max_inactive_connection_lifetime,
            **connect_kwargs)
        return pool

    # noinspection PyUnresolvedReferences
    async def all(self, clause, *multiparams, bind=None, **params):
        if bind is None:
            bind = self.bind
        query, args = self.compile(clause, *multiparams, **params)
        rv = await bind.fetch(query, *args)

        model = self.guess_model(clause)
        if model is not None:
            rv = list(map(model.from_row, rv))

        return rv

    # noinspection PyUnresolvedReferences
    async def first(self, clause, *multiparams, bind=None, **params):
        if bind is None:
            bind = self.bind
        query, args = self.compile(clause, *multiparams, **params)
        rv = await bind.fetchrow(query, *args)

        model = self.guess_model(clause)
        if model is not None:
            rv = model.from_row(rv)

        return rv

    # noinspection PyUnresolvedReferences
    async def scalar(self, clause, *multiparams, bind=None, **params):
        if bind is None:
            bind = self.bind
        query, args = self.compile(clause, *multiparams, **params)
        return await bind.fetchval(query, *args)

    # noinspection PyUnresolvedReferences
    def iterate(self, clause, *multiparams, connection=None, **params):
        if connection is None:
            connection = self.bind
        assert isinstance(connection, Connection)
        query, args = self.compile(clause, *multiparams, **params)
        rv = connection.cursor(query, *args)

        model = self.guess_model(clause)
        if model is not None:
            rv = model.map(rv)

        return rv

    def acquire(self, *, timeout=None):
        # noinspection PyUnresolvedReferences
        return GinoAcquireContext(self.bind, timeout)

    async def release(self, connection):
        # noinspection PyUnresolvedReferences
        return await self.bind.release(connection)

    def transaction(self, *, isolation='read_committed', readonly=False,
                    deferrable=False):
        # noinspection PyUnresolvedReferences
        return GinoTransaction(self, isolation, readonly, deferrable)
