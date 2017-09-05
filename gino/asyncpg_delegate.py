import asyncio
import sys
from collections import deque

from asyncpg.pool import Pool
from asyncpg.connection import Connection
import sqlalchemy as sa
from sqlalchemy.sql.base import Executable
from sqlalchemy.dialects import postgresql as sa_pg

from .crud import CRUDModel
from .dialect import AsyncpgDialect, GinoCursorFactory
from .local import get_local
from .declarative import declarative_base
from . import json_support


class GinoPool(Pool):
    def __init__(self, metadata, *connect_args, min_size, max_size,
                 max_queries, max_inactive_connection_lifetime, setup, init,
                 loop, connection_class, **connect_kwargs):
        self.metadata = metadata
        self._execution_options = {}
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

    @property
    def execution_options(self):
        return self._execution_options

    async def _acquire(self, timeout):
        conn = await super()._acquire(timeout)
        conn.execution_options.clear()
        conn.execution_options.update(self._execution_options)
        return conn

    async def release(self, connection):
        connection.execution_options.clear()
        return await super().release(connection)

    async def all(self, clause, *multiparams, **params):
        return await self.metadata.all(clause, *multiparams, **params,
                                       bind=self)

    async def first(self, clause, *multiparams, **params):
        return await self.metadata.first(clause, *multiparams, **params,
                                         bind=self)

    async def scalar(self, clause, *multiparams, **params):
        return await self.metadata.scalar(clause, *multiparams, **params,
                                          bind=self)

    async def status(self, clause, *multiparams, **params):
        return await self.metadata.status(clause, *multiparams, **params,
                                          bind=self)

    async def executemany(self, clause, args, **params):
        with await self._acquire(params.get('timeout', None)) as conn:
            return self.metadata.executemany(clause, args, **params, bind=conn)


class GinoConnection(Connection):
    metadata = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._execution_options = {}

    @property
    def execution_options(self):
        return self._execution_options

    async def all(self, clause, *multiparams, **params):
        return await self.metadata.all(clause, *multiparams, **params,
                                       bind=self)

    async def first(self, clause, *multiparams, **params):
        return await self.metadata.first(clause, *multiparams, **params,
                                         bind=self)

    async def scalar(self, clause, *multiparams, **params):
        return await self.metadata.scalar(clause, *multiparams, **params,
                                          bind=self)

    async def status(self, clause, *multiparams, **params):
        return await self.metadata.status(clause, *multiparams, **params,
                                          bind=self)

    def iterate(self, clause, *multiparams, **params):
        return self.metadata.iterate(clause, *multiparams, **params,
                                     connection=self)

    async def executemany(self, clause, args, **params):
        return self.metadata.executemany(clause, args, **params, bind=self)


class LazyConnection:
    """
    Use :class:`LazyConnection` to create a lazy connection which does not
    immediately return a connection on creation. User should explicitly call
    :meth:`get` to get a real connection when needed. And :meth:`release`
    should be called when the real connection is no longer needed. Both methods
    can be called multiple times.
    """
    def __init__(self, pool, timeout):
        self._pool = pool
        self._ctx = None
        self._conn = None
        self._timeout = timeout

    async def get(self):
        if self._conn is None:
            self._ctx = self._pool.acquire(timeout=self._timeout)
            self._conn = connection = await self._ctx.__aenter__()
        else:
            connection = self._conn
        return connection

    async def release(self, args):
        if self._ctx is not None:
            ctx, self._ctx = self._ctx, None
            self._conn = None
            await ctx.__aexit__(*args)


class GinoAcquireContext:
    def __init__(self, bind, timeout, reuse, lazy):
        self._used = False
        self._bind = bind
        self._timeout = timeout
        self._reuse = reuse
        self._pop = False
        self._lazy = lazy
        self._lazy_conn = None

    async def __aenter__(self):
        if self._used:
            raise RuntimeError('GinoAcquireContext is entered twice')
        self._used = True

        local = get_local()
        if self._reuse and local:
            stack = local.get('connection_stack')
            if stack:
                conn = stack[-1]
                if not self._lazy:
                    conn = await conn.get()
                return conn

        if isinstance(self._bind, Pool):
            self._lazy_conn = conn = LazyConnection(self._bind, self._timeout)
            if local is not None:
                local.setdefault('connection_stack', deque()).append(conn)
                self._pop = True
            if not self._lazy:
                conn = await conn.get()
            return conn
        else:
            return self._bind

    async def __aexit__(self, *exc):
        try:
            if self._pop:
                ctx = get_local() or {}
                stack = ctx.get('connection_stack')
                if stack:
                    stack.pop()
                    if not stack:
                        ctx.pop('connection_stack')
        finally:
            conn, self._lazy_conn = self._lazy_conn, None
            if conn is not None:
                await conn.release(exc)


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
        try:
            await self._ctx.__aexit__(extype, ex, tb)
        except:
            await self._conn_ctx.__aexit__(*sys.exc_info())
            raise
        else:
            await self._conn_ctx.__aexit__(extype, ex, tb)


class Gino(sa.MetaData):
    def __init__(self, bind=None, dialect=None, model_class=CRUDModel,
                 **kwargs):
        self._bind = None
        super().__init__(bind=bind, **kwargs)
        self.dialect = dialect or AsyncpgDialect()
        self.Model = declarative_base(self, model_class)
        for mod in sa, sa_pg, json_support:
            for key in mod.__all__:
                if not hasattr(self, key):
                    setattr(self, key, getattr(mod, key))

    @property
    def bind(self):
        return self.get_bind

    # noinspection PyMethodOverriding
    @bind.setter
    def bind(self, val):
        self._bind = val

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
        pool = GinoPool(
            self, dsn,
            connection_class=connection_class,
            min_size=min_size, max_size=max_size,
            max_queries=max_queries, loop=loop, setup=setup, init=init,
            max_inactive_connection_lifetime=max_inactive_connection_lifetime,
            **connect_kwargs)
        return pool

    async def get_bind(self, bind=None):
        if bind is None:
            local = get_local()
            if local:
                stack = local.get('connection_stack')
                if stack:
                    bind = await stack[-1].get()
            if bind is None:
                bind = self._bind
        return bind

    def compile(self, elem, *multiparams, **params):
        return self.dialect.compile(elem, *multiparams, **params)

    async def all(self, clause, *multiparams, bind=None, **params):
        bind = await self.get_bind(bind)
        return await self.dialect.do_all(bind, clause, *multiparams, **params)

    async def first(self, clause, *multiparams, bind=None, **params):
        bind = await self.get_bind(bind)
        return await self.dialect.do_first(
            bind, clause, *multiparams, **params)

    async def scalar(self, clause, *multiparams, bind=None, **params):
        bind = await self.get_bind(bind)
        return await self.dialect.do_scalar(
            bind, clause, *multiparams, **params)

    async def status(self, clause, *multiparams, bind=None, **params):
        bind = await self.get_bind(bind)
        return await self.dialect.do_status(
            bind, clause, *multiparams, **params)

    async def executemany(self, clause, args, bind=None, **params):
        bind = await self.get_bind(bind)
        return await self.dialect.do_executemany(bind, clause, args, **params)

    def iterate(self, clause, *multiparams, connection=None, **params):
        async def env_factory():
            return await self.get_bind(connection), self
        return GinoCursorFactory(env_factory, clause, multiparams, params)

    def acquire(self, *, timeout=None, reuse=True, lazy=False):
        return GinoAcquireContext(self._bind, timeout, reuse, lazy)

    def transaction(self, *, isolation='read_committed', readonly=False,
                    deferrable=False, timeout=None, reuse=True):
        return GinoTransaction(self.acquire(timeout=timeout, reuse=reuse),
                               isolation, readonly, deferrable)


class GinoExecutor:
    def __init__(self, query):
        self._query = query

    @property
    def query(self):
        return self._query

    async def get_bind(self, bind):
        if bind is None:
            bind = self._query.bind
            if callable(bind):
                bind = bind()
                if asyncio.iscoroutine(bind):
                    bind = await bind
        return bind

    async def all(self, *multiparams, bind=None, **params):
        bind = await self.get_bind(bind)
        return await bind.metadata.dialect.do_all(
            bind, self._query, *multiparams, **params)

    async def first(self, *multiparams, bind=None, **params):
        bind = await self.get_bind(bind)
        return await bind.metadata.dialect.do_first(
            bind, self._query, *multiparams, **params)

    async def scalar(self, *multiparams, bind=None, **params):
        bind = await self.get_bind(bind)
        return await bind.metadata.dialect.do_scalar(
            bind, self._query, *multiparams, **params)

    async def status(self, *multiparams, bind=None, **params):
        """
        You can parse the return value like this: https://git.io/v7oze
        """
        bind = await self.get_bind(bind)
        return await bind.metadata.dialect.do_status(
            bind, self._query, *multiparams, **params)

    async def executemany(
            self, command: str, args, *, timeout: float=None, bind=None):
        bind = await self.get_bind(bind)
        return await bind.metadata.dialect.do_executemany(
            bind, command, args, timeout
        )

    def iterate(self, *multiparams, connection=None, **params):
        async def env_factory():
            bind = await self.get_bind(connection)
            return bind, bind.metadata
        return GinoCursorFactory(env_factory, self._query, multiparams, params)


Executable.gino = property(GinoExecutor)
