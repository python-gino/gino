import asyncio
import functools
import types
from collections import deque

try:
    from contextvars import ContextVar
except ImportError:
    from aiocontextvars import ContextVar
# noinspection PyProtectedMember
from asyncpg.connection import _ConnectionProxy
from asyncpg.exceptions import InterfaceError
from sqlalchemy.engine import Engine as SAEngine

from .local import get_local
from .connection import Connection
from .exceptions import InterfaceError
from .utils import Deferred


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
                 '_conn_task', '_metadata', '_execution_options',
                 '_wrap_cache')

    def __init__(self, pool, timeout, root, conn_cls):
        self._pool = pool
        self._timeout = timeout
        self._root = root or self
        self._conn_cls = conn_cls
        self._conn = None
        self._conn_task = None
        self._metadata = pool.metadata
        self._execution_options = dict(pool.execution_options)
        self._closed = False
        self._wrap_cache = {}

    @property
    def metadata(self):
        return self._metadata

    @property
    def execution_options(self):
        return self._execution_options

    @property
    def is_root(self):
        return self._root is self

    async def get_connection(self):
        if self._closed:
            raise InterfaceError('This LazyConnection is returned to pool')
        if self._root is self:
            if self._conn_task is None:
                sup = super(GinoPool, self._pool)
                self._conn_task = self._pool.loop.create_task(
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
                sup = super(GinoPool, self._pool)
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


class GinoTransaction:
    __slots__ = ('_pool', '_isolation', '_readonly', '_deferrable', '_timeout',
                 '_reuse', '_future')

    def __init__(self, pool, isolation, readonly, deferrable, timeout, reuse):
        self._pool = pool
        self._isolation = isolation
        self._readonly = readonly
        self._deferrable = deferrable
        self._timeout = timeout
        self._reuse = reuse
        self._future = True

    async def _get_conn_tx(self, *, closing=False):
        fut = self._future
        if fut is False:
            raise InterfaceError('the transaction is already closed')
        if closing:
            self._future = False
            if fut is True:
                raise InterfaceError('the transaction is never started')
        elif fut is True:
            fut = self._future = self._pool.loop.create_task(
                self._get_conn_tx_impl())
        return await fut

    async def _get_conn_tx_impl(self):
        conn = await self._pool.acquire(timeout=self._timeout,
                                        reuse=self._reuse)
        tx = conn.transaction(isolation=self._isolation,
                              readonly=self._readonly,
                              deferrable=self._deferrable)
        return conn, tx

    async def __aenter__(self):
        conn, tx = await self._get_conn_tx()
        await tx.__enter__()
        return conn

    async def __aexit__(self, extype, ex, tb):
        conn, tx = await self._get_conn_tx(closing=True)
        try:
            await tx.__aexit__(extype, ex, tb)
        finally:
            await self._pool.release(conn)

    async def start(self):
        conn, tx = await self._get_conn_tx()
        await tx.start()
        return conn

    async def commit(self):
        conn, tx = await self._get_conn_tx(closing=True)
        try:
            await tx.commit()
        finally:
            await self._pool.release(conn)

    async def rollback(self):
        conn, tx = await self._get_conn_tx(closing=True)
        try:
            await tx.rollback()
        finally:
            await self._pool.release(conn)


class EngineNew:
    __slots__ = ('_metadata', '_execution_options')

    def __init__(self):
        self._execution_options = {}

    @classmethod
    async def create(cls, *connect_args, min_size, max_size,
                 max_queries, max_inactive_connection_lifetime, setup, init,
                 loop, connection_class, **connect_kwargs):
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
        conn = LazyConnection(self, timeout, root, self._connection_class)
        if local is not None:
            local.setdefault('connection_stack', deque()).append(conn)
        if not lazy:
            try:
                await conn.get_connection()
            except Exception:
                await self.release(conn)
                raise
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

    def transaction(self, *, isolation='read_committed', readonly=False,
                    deferrable=False, timeout=None, reuse=True):
        return GinoTransaction(
            self, isolation, readonly, deferrable, timeout, reuse)

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

    @property
    def loop(self):
        return self._loop

    async def all(self, clause, *multiparams, **params):
        async with self.acquire(reuse=True) as conn:
            return await self.dialect.do_all(conn, clause,
                                             *multiparams, **params)

    async def first(self, clause, *multiparams, **params):
        async with self.acquire(reuse=True) as conn:
            return await self.dialect.do_first(conn, clause,
                                               *multiparams, **params)

    async def scalar(self, clause, *multiparams, **params):
        async with self.acquire(reuse=True) as conn:
            return await self.dialect.do_scalar(conn, clause,
                                                *multiparams, **params)

    async def status(self, clause, *multiparams, **params):
        async with self.acquire(reuse=True) as conn:
            return await self.dialect.do_status(conn, clause,
                                                *multiparams, **params)


# noinspection PyAbstractClass
class SAEngineAdaptor(SAEngine):
    def __init__(self, dialect):
        super().__init__(None, dialect, '')


class AcquireContext:
    def __init__(self, conn_factory, reuse, kwargs):
        self._conn_factory = conn_factory
        self._reuse = reuse
        self._kwargs = kwargs
        self._conn = None

    async def __aenter__(self):
        if self._conn is not None:
            raise InterfaceError('entering twice')
        root = None
        local = get_local()
        if self._reuse and local:
            stack = local.get('connection_stack')
            if stack:
                root = getattr(stack[-1], '_root')
        self._conn = conn = self._conn_factory(self._kwargs, root)
        if local is not None:
            local.setdefault('connection_stack', deque()).append(conn)
        return conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        conn, self._conn = self._conn, None
        if conn is None:
            raise InterfaceError('never entered')
        try:
            local = get_local()
            if local is not None:
                if conn is not local['connection_stack'].pop():
                    raise InterfaceError('wrong exit order')
        finally:
            await conn.release(close=True)


class AsyncExecution:
    def __init__(self, engine, method, args, kwargs):
        self._engine = engine
        self._method = method
        self._args = args
        self._kwargs = kwargs

    async def _run(self):
        async with self._engine.acquire() as conn:
            return await getattr(conn, self._method)(*self._args,
                                                     **self._kwargs)

    def __await__(self):
        return self._run().__await__()

    def __getattr__(self, item):
        async def _wrapper(*args, **kwargs):
            async with self._engine.acquire() as conn:
                rv = await getattr(conn, self._method)(*self._args,
                                                       **self._kwargs)
                return await getattr(rv, item)(*args, **kwargs)
        return _wrapper


class EngineMethod:
    def __init__(self):
        self._name = None

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            # noinspection PyArgumentList
            return types.MethodType(self, instance)

    def __call__(self, engine, *args, **kwargs):
        return AsyncExecution(engine, self._name, args, kwargs)


class TransactionContext:
    def __init__(self, conn, transaction, close_with_result):
        self.conn = conn
        self.transaction = transaction
        self.close_with_result = close_with_result

    async def __aenter__(self):
        await self.transaction.start()
        return self.conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.transaction.rollback()
        else:
            await self.transaction.commit()
        if not self.close_with_result:
            await self.conn.close()


class Engine(SAEngine):
    _connection_cls = Connection

    def __init__(self, pool, dialect, url, logging_name=None, echo=None,
                 proxy=None, execution_options=None, loop=None):
        super().__init__(pool, dialect, url, logging_name, echo, proxy,
                         execution_options)
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self._conn_ctx = ContextVar('gino-conn', default=None)

    # API

    # def acquire(self, *, reuse=True, **kwargs):
    #     return AcquireContext(self._new_connection, reuse, kwargs)

    # Internal API

    # def _new_connection(self, kwargs, root):
    #     return self._connection_cls(self, kwargs, root=root, loop=self._loop)
    #
    # async def _acquire(self, kwargs):
    #     return await self.pool.acquire(kwargs)
    #
    # async def _release(self, conn):
    #     return await self.pool.release(conn)
    #
    # execute = EngineMethod()
    # _execute_clauseelement = EngineMethod()

    async def _async_init(self):
        await self.pool
        return self

    def __await__(self):
        return self._async_init().__await__()

    def _wrap_pool_connect(self, fn, connection):
        super_connect = super()._wrap_pool_connect

        async def _connect():
            try:
                rv = await fn()

                def func():
                    return rv
            except Exception as e:
                rv = e

                def func():
                    raise rv
            return super_connect(func, connection)
        return Deferred(_connect(), loop=self.loop)

    def create(self, entity, **kwargs):
        pass

    def _run_visitor(self, visitor_callable, element, **kwargs):
        pass

    _trans_ctx = TransactionContext

    def begin(self, *args, close_with_result=False, **kwargs):
        conn = self.contextual_connect(close_with_result=close_with_result)
        trans = conn.begin(*args, **kwargs)
        return self._trans_ctx(conn, trans, close_with_result)

    def contextual_connect(self, close_with_result=False, **kwargs):
        # noinspection PyNoneFunctionAssignment
        rv = self._conn_ctx.get()
        if rv is None:
            rv = super().contextual_connect(close_with_result, **kwargs)
            self._conn_ctx.set(rv)
        else:
            rv = rv.contextual_connect(close_with_result=close_with_result)
        return rv

    def scalar(self, obj, *multiparams, **params):
        pass

    def drop(self, entity, **kwargs):
        pass
