import asyncio
import functools
import types
from collections import deque

# noinspection PyProtectedMember
from asyncpg.connection import _ConnectionProxy
from asyncpg.exceptions import InterfaceError
from asyncpg.pool import Pool

from .local import get_local


class LazyConnection(_ConnectionProxy):
    """
    Use :class:`LazyConnection` to create a lazy connection which does not 
    immediately return a connection on creation. Connection is acquired before
    any public async method. User should explicitly call :meth:`get_connection`
    to get a real connection before calling public sync methods. And
    :meth:`release` should be called when the real connection is no longer 
    needed. Both methods can be called multiple times, and are coroutine-safe.
    """

    __slots__ = ('_pool', '_timeout', '_root', '_conn_cls', '_conn', '_closed',
                 '_conn_task', '_metadata', '_execution_options', '_loop',
                 '_wrap_cache')

    def __init__(self, pool, timeout, root, conn_cls, loop):
        self._pool = pool
        self._timeout = timeout
        self._root = root or self
        self._conn_cls = conn_cls
        self._conn = None
        self._conn_task = None
        self._metadata = pool.metadata
        self._execution_options = dict(pool.execution_options)
        self._loop = loop
        self._closed = False
        self._wrap_cache = {}

    @property
    def metadata(self):
        return self._metadata

    @property
    def execution_options(self):
        return self._execution_options

    async def get_connection(self):
        if self._closed:
            raise InterfaceError('This LazyConnection is returned to pool')
        if self._root is self:
            if self._conn_task is None:
                sup = super(self._pool.__class__, self._pool)
                self._conn_task = self._loop.create_task(
                    getattr(sup, '_acquire')(timeout=self._timeout))
            self._conn = await self._conn_task
            getattr(self._conn, '_set_metadata')(self._metadata)
        elif self._conn is None:
            self._conn = await self._root.get_connection()
        return self._conn

    async def release(self, close=False):
        self._closed = self._closed or close
        rv = None
        try:
            conn_to_release = None
            if self._conn_task is not None:
                fut, self._conn_task = self._conn_task, None
                conn_to_release = await fut
            if self._conn is not None:
                getattr(self._conn, '_set_metadata')(None)
            if conn_to_release is not None:
                sup = super(self._pool.__class__, self._pool)
                rv = await getattr(sup, 'release')(conn_to_release)
        finally:
            self._conn = None
        return rv

    def __getattr__(self, attr):
        rv = self._wrap_cache.get(attr)
        if rv is not None:
            # noinspection PyArgumentList
            return types.MethodType(rv, self)
        cls_val = getattr(self._conn_cls, attr)
        if asyncio.iscoroutinefunction(cls_val):
            @functools.wraps(cls_val)
            async def wrapper(_, *args, **kwargs):
                conn = await self.get_connection()
                return await getattr(conn, attr)(*args, **kwargs)
            self._wrap_cache[attr] = wrapper
            # noinspection PyArgumentList
            return types.MethodType(wrapper, self)
        if self._conn is None:
            raise InterfaceError(
                'Connection is not ready yet, or has been released')
        return getattr(self._conn, attr)


class GinoAcquireContext:
    __slots__ = ('timeout', 'connection', 'done', 'pool', '_reuse', '_lazy')

    def __init__(self, pool, timeout, reuse, lazy):
        self.pool = pool
        self.timeout = timeout
        self.connection = None
        self.done = False
        self._reuse = reuse
        self._lazy = lazy

    async def __aenter__(self):
        if self.connection is not None or self.done:
            raise InterfaceError('a connection is already acquired')
        self.connection = await getattr(self.pool, '_acquire')(
            self.timeout, reuse=self._reuse, lazy=self._lazy)
        return self.connection

    async def __aexit__(self, *exc):
        self.done = True
        con = self.connection
        self.connection = None
        await self.pool.release(con)

    def __await__(self):
        self.done = True
        return getattr(self.pool, '_acquire')(
            self.timeout, reuse=self._reuse, lazy=self._lazy).__await__()


class GinoPool(Pool):
    __slots__ = ('_metadata', '_execution_options')

    def __init__(self, metadata, *connect_args, min_size, max_size,
                 max_queries, max_inactive_connection_lifetime, setup, init,
                 loop, connection_class, **connect_kwargs):
        self._metadata = metadata
        self._execution_options = {}

        super().__init__(
            *connect_args, min_size=min_size, max_size=max_size,
            max_queries=max_queries,
            max_inactive_connection_lifetime=max_inactive_connection_lifetime,
            setup=setup, init=init, loop=loop,
            connection_class=connection_class, **connect_kwargs)

    async def _async__init__(self):
        rv = await super()._async__init__()
        if getattr(self._metadata, '_bind') is None:
            self._metadata.bind = self
        return rv

    async def close(self):
        if getattr(self._metadata, '_bind') is self:
            self._metadata.bind = None
        self._metadata = None
        return await super().close()

    def acquire(self, *, timeout=None, reuse=False, lazy=False):
        return GinoAcquireContext(self, timeout, reuse, lazy)

    async def _acquire(self, timeout, reuse=False, lazy=False):
        root = None
        local = get_local()
        if reuse and local:
            stack = local.get('connection_stack')
            if stack:
                root = getattr(stack[-1], '_root')
        conn = LazyConnection(self, timeout, root, self._connection_class,
                              self._loop)
        if local is not None:
            local.setdefault('connection_stack', deque()).append(conn)
        if not lazy:
            await conn.get_connection()
        return conn

    async def release(self, connection):
        if type(connection) is not LazyConnection or \
                getattr(connection, '_pool', None) is not self:
            raise InterfaceError(
                'Pool.release() received invalid connection: '
                '{connection!r} is not a member of this pool'.format(
                    connection=connection))

        ctx = get_local()
        if ctx is not None:
            stack = ctx.get('connection_stack')
            if not stack or stack[-1] is not connection:
                raise InterfaceError('Wrong release order')
            stack.pop()
            if not stack:
                ctx.pop('connection_stack')

        return await connection.release(close=True)

    @staticmethod
    def get_current_connection():
        local = get_local()
        if local:
            stack = local.get('connection_stack')
            if stack:
                return stack[-1]

    @property
    def execution_options(self):
        return self._execution_options

    @property
    def metadata(self):
        return self._metadata

    @property
    def dialect(self):
        return self._metadata.dialect

    async def all(self, clause, *multiparams, **params):
        return await self.dialect.do_all(self, clause,
                                         *multiparams, **params)

    async def first(self, clause, *multiparams, **params):
        return await self.dialect.do_first(self, clause,
                                           *multiparams, **params)

    async def scalar(self, clause, *multiparams, **params):
        return await self.dialect.do_scalar(self, clause,
                                            *multiparams, **params)

    async def status(self, clause, *multiparams, **params):
        return await self.dialect.do_status(self, clause,
                                            *multiparams, **params)
