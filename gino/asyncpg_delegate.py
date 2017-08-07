import sys
from collections import deque

from asyncpg.pool import Pool
from asyncpg.connection import Connection
from sqlalchemy.sql.base import Executable

from .local import get_local


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

    async def all(self, clause, *multiparams, timeout=None, **params):
        return await self.metadata.all(clause, *multiparams, **params,
                                       timeout=timeout, bind=self)

    async def first(self, clause, *multiparams, timeout=None, **params):
        return await self.metadata.first(clause, *multiparams, **params,
                                         timeout=timeout, bind=self)

    async def scalar(self, clause, *multiparams, timeout=None, **params):
        return await self.metadata.scalar(clause, *multiparams, **params,
                                          timeout=timeout, bind=self)

    async def status(self, clause, *multiparams, timeout=None, **params):
        return await self.metadata.status(clause, *multiparams, **params,
                                          timeout=timeout, bind=self)


class GinoConnection(Connection):
    metadata = None

    async def all(self, clause, *multiparams, timeout=None, **params):
        return await self.metadata.all(clause, *multiparams, **params,
                                       timeout=timeout, bind=self)

    async def first(self, clause, *multiparams, timeout=None, **params):
        return await self.metadata.first(clause, *multiparams, **params,
                                         timeout=timeout, bind=self)

    async def scalar(self, clause, *multiparams, timeout=None, **params):
        return await self.metadata.scalar(clause, *multiparams, **params,
                                          timeout=timeout, bind=self)

    async def status(self, clause, *multiparams, timeout=None, **params):
        return await self.metadata.status(clause, *multiparams, **params,
                                          timeout=timeout, bind=self)

    def iterate(self, clause, *multiparams, timeout=None, **params):
        return self.metadata.iterate(clause, *multiparams, **params,
                                     timeout=timeout, connection=self)


class GinoAcquireContext:
    def __init__(self, bind, timeout, reuse):
        self._used = False
        self._bind = bind
        self._timeout = timeout
        self._ctx = None
        self._reuse = reuse
        self._pop = False

    async def __aenter__(self):
        if self._used:
            raise RuntimeError('GinoAcquireContext is entered twice')
        self._used = True

        local = get_local()
        if self._reuse and local:
            stack = local.get('connection_stack')
            if stack:
                return stack[-1]

        if isinstance(self._bind, Pool):
            self._ctx = self._bind.acquire(timeout=self._timeout)
            conn = await self._ctx.__aenter__()
            if local is not None:
                local.setdefault('connection_stack', deque()).append(conn)
                self._pop = True
            return conn
        else:
            return self._bind

    async def __aexit__(self, *exc):
        if self._pop:
            ctx = get_local() or {}
            stack = ctx.get('connection_stack')
            if stack:
                stack.pop()
                if not stack:
                    ctx.pop('connection_stack')
        if self._ctx is not None:
            await self._ctx.__aexit__(*exc)


class GinoTransaction:
    def __init__(self, conn_ctx, isolation, readonly, deferrable):
        self._conn_ctx = conn_ctx
        self._isolation = isolation
        self._readonly = readonly
        self._deferrable = deferrable
        self._ctx = None

    async def __aenter__(self):
        conn = await self._conn_ctx.__aenter__()
        self._ctx = conn.transaction(isolation=self._isolation,
                                     readonly=self._readonly,
                                     deferrable=self._deferrable)
        return conn, await self._ctx.__aenter__()

    async def __aexit__(self, extype, ex, tb):
        # noinspection PyBroadException
        try:
            await self._ctx.__aexit__(extype, ex, tb)
        except:
            await self._conn_ctx.__aexit__(*sys.exc_info())
        else:
            await self._conn_ctx.__aexit__(extype, ex, tb)


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

    def get_bind(self, bind=None):
        if bind is None:
            local = get_local()
            if local:
                stack = local.get('connection_stack')
                if stack:
                    bind = stack[-1]
            if bind is None:
                # noinspection PyUnresolvedReferences
                bind = self.bind
        return bind

    async def all(self, clause, *multiparams,
                  bind=None, timeout=None, **params):
        bind = self.get_bind(bind)
        # noinspection PyUnresolvedReferences
        query, args = self.compile(clause, *multiparams, **params)
        rv = await bind.fetch(query, *args, timeout=timeout)

        # noinspection PyUnresolvedReferences
        model = self.guess_model(clause)
        if model is not None:
            rv = list(map(model.from_row, rv))

        return rv

    # noinspection PyUnresolvedReferences
    async def first(self, clause, *multiparams, bind=None,
                    timeout=None, **params):
        bind = self.get_bind(bind)
        # noinspection PyUnresolvedReferences
        query, args = self.compile(clause, *multiparams, **params)
        rv = await bind.fetchrow(query, *args, timeout=timeout)

        # noinspection PyUnresolvedReferences
        model = self.guess_model(clause)
        if model is not None:
            rv = model.from_row(rv)

        return rv

    # noinspection PyUnresolvedReferences
    async def scalar(self, clause, *multiparams, bind=None,
                     timeout=None, **params):
        bind = self.get_bind(bind)
        query, args = self.compile(clause, *multiparams, **params)
        return await bind.fetchval(query, *args, timeout=timeout)

    async def status(self, clause, *multiparams, bind=None,
                     timeout=None, **params):
        bind = self.get_bind(bind)
        # noinspection PyUnresolvedReferences
        query, args = self.compile(clause, *multiparams, **params)
        return await bind.execute(query, *args, timeout=timeout)

    def iterate(self, clause, *multiparams, connection=None,
                timeout=None, **params):
        connection = self.get_bind(connection)
        assert isinstance(connection, Connection)
        # noinspection PyUnresolvedReferences
        query, args = self.compile(clause, *multiparams, **params)
        rv = connection.cursor(query, *args, timeout=timeout)

        # noinspection PyUnresolvedReferences
        model = self.guess_model(clause)
        if model is not None:
            rv = model.map(rv)

        return rv

    def acquire(self, *, timeout=None, reuse=True):
        # noinspection PyUnresolvedReferences
        return GinoAcquireContext(self.bind, timeout, reuse)

    def transaction(self, *, isolation='read_committed', readonly=False,
                    deferrable=False, timeout=None, reuse=True):
        return GinoTransaction(self.acquire(timeout=timeout, reuse=reuse),
                               isolation, readonly, deferrable)


class GinoExecutor:
    def __init__(self, query):
        self.query = query
        self.gino = query.__model__.__metadata__

    def all(self, *args, **kwargs):
        return self.gino.all(self.query, *args, **kwargs)

    def first(self, *args, **kwargs):
        return self.gino.first(self.query, *args, **kwargs)

    def scalar(self, *args, **kwargs):
        return self.gino.scalar(self.query, *args, **kwargs)

    def status(self, *args, **kwargs):
        """
        You can parse the return value like this: https://git.io/v7oze
        """
        return self.gino.status(self.query, *args, **kwargs)

    def iterate(self, *args, **kwargs):
        return self.gino.iterate(self.query, *args, **kwargs)


Executable.gino = property(GinoExecutor)
