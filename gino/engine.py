import asyncio
import collections
import functools
import sys
import time

from sqlalchemy.engine import Engine, Connection
from sqlalchemy.sql import schema

from .transaction import GinoTransaction


def _get_context_var():
    try:
        # noinspection PyPackageRequirements
        from contextvars import ContextVar
    except ImportError:
        try:
            # noinspection PyPackageRequirements
            from aiocontextvars import ContextVar
        except ImportError:
            class ContextVar:
                def __init__(self, name, default=None):
                    self._name = name
                    self._default = default

                @property
                def name(self):
                    return self._name

                @property
                def default(self):
                    return self._default

                def get(self, default=None):
                    raise LookupError

                def set(self, val):
                    pass

                def delete(self):
                    raise LookupError
    return ContextVar


class BaseDBAPIConnection:
    _reset_agent = None
    gino_conn = None

    def __init__(self, cursor_cls):
        self._cursor_cls = cursor_cls
        self._closed = False

    def commit(self):
        pass

    def cursor(self):
        return self._cursor_cls(self)

    @property
    def raw_connection(self):
        raise NotImplementedError

    async def acquire(self, *, timeout=None):
        if self._closed:
            raise ValueError(
                'This connection is already released permanently.')
        return await self._acquire(timeout)

    async def _acquire(self, timeout):
        raise NotImplementedError

    async def release(self, permanent):
        if permanent:
            self._closed = True
        return await self._release()

    async def _release(self):
        raise NotImplementedError


class DBAPIConnection(BaseDBAPIConnection):
    def __init__(self, cursor_cls, pool=None):
        super().__init__(cursor_cls)
        self._pool = pool
        self._conn = None
        self._lock = asyncio.Lock()

    @property
    def raw_connection(self):
        return self._conn

    async def _acquire(self, timeout):
        try:
            if timeout is None:
                await self._lock.acquire()
            else:
                before = time.monotonic()
                await asyncio.wait_for(self._lock.acquire(), timeout=timeout)
                after = time.monotonic()
                timeout -= after - before
            if self._conn is None:
                self._conn = await self._pool.acquire(timeout=timeout)
            return self._conn
        finally:
            self._lock.release()

    async def _release(self):
        conn, self._conn = self._conn, None
        if conn is None:
            return False
        await self._pool.release(conn)
        return True


class ReusingDBAPIConnection(BaseDBAPIConnection):
    def __init__(self, cursor_cls, root):
        super().__init__(cursor_cls)
        self._root = root

    @property
    def raw_connection(self):
        return self._root.raw_connection

    async def _acquire(self, timeout):
        return await self._root.acquire(timeout=timeout)

    async def _release(self):
        pass


# noinspection PyAbstractClass
class SAConnection(Connection):
    pass


# noinspection PyAbstractClass
class SAEngine(Engine):
    _connection_cls = SAConnection

    def __init__(self, dialect, **kwargs):
        super().__init__(None, dialect, None, **kwargs)


class AcquireContext:
    __slots__ = ['_acquire', '_release']

    def __init__(self, acquire, release):
        self._acquire = acquire
        self._release = release

    async def __aenter__(self):
        rv = await self._acquire()
        self._release = functools.partial(self._release, rv)
        return rv

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._release()

    def __await__(self):
        return self._acquire().__await__()


class TransactionContext:
    __slots__ = ['_conn_ctx', '_tx_ctx']

    def __init__(self, conn_ctx, args):
        self._conn_ctx = conn_ctx
        self._tx_ctx = args

    async def __aenter__(self):
        conn = await self._conn_ctx.__aenter__()
        try:
            args, kwargs = self._tx_ctx
            self._tx_ctx = conn.transaction(*args, **kwargs)
            return await self._tx_ctx.__aenter__()
        except Exception:
            await self._conn_ctx.__aexit__(*sys.exc_info())
            raise

    async def __aexit__(self, *exc_info):
        try:
            tx, self._tx_ctx = self._tx_ctx, None
            return await tx.__aexit__(*exc_info)
        except Exception:
            exc_info = sys.exc_info()
            raise
        finally:
            await self._conn_ctx.__aexit__(*exc_info)


class GinoConnection:
    # noinspection PyProtectedMember
    schema_for_object = schema._schema_getter(None)

    def __init__(self, dialect, sa_conn, stack=None):
        self._dialect = dialect
        self._sa_conn = sa_conn
        self._stack = stack

    @property
    def _dbapi_conn(self):
        return self._sa_conn.connection

    @property
    def raw_connection(self):
        return self._dbapi_conn.raw_connection

    async def get_raw_connection(self, *, timeout=None):
        return await self._dbapi_conn.acquire(timeout=timeout)

    async def release(self, *, permanent=False):
        if permanent and self._stack is not None:
            for i in range(len(self._stack)):
                if self._stack[-1].gino_conn is self:
                    dbapi_conn = self._stack.pop()
                    self._stack.rotate(-i)
                    await dbapi_conn.release(True)
                    break
                else:
                    self._stack.rotate()
            else:
                raise ValueError('This connection is already released.')
        else:
            await self._dbapi_conn.release(permanent)

    @property
    def dialect(self):
        return self._dialect

    def _execute(self, clause, multiparams, params):
        return self._sa_conn.execute(clause, *multiparams, **params)

    async def all(self, clause, *multiparams, **params):
        result = self._execute(clause, multiparams, params)
        return await result.execute()

    async def first(self, clause, *multiparams, **params):
        result = self._execute(clause, multiparams, params)
        return await result.execute(one=True)

    async def scalar(self, clause, *multiparams, **params):
        result = self._execute(clause, multiparams, params)
        rv = await result.execute(one=True, return_model=False)
        if rv:
            return rv[0]
        else:
            return None

    async def status(self, clause, *multiparams, **params):
        """
        You can parse the return value like this: https://git.io/v7oze
        """
        result = self._execute(clause, multiparams, params)
        return await result.execute(status=True)

    def transaction(self, *args, **kwargs):
        return GinoTransaction(self, args, kwargs)

    def iterate(self, clause, *multiparams, **params):
        result = self._execute(clause, multiparams, params)
        return result.iterate()

    def execution_options(self, **opt):
        return type(self)(self._dialect,
                          self._sa_conn.execution_options(**opt))

    async def _run_visitor(self, visitorcallable, element, **kwargs):
        await visitorcallable(self.dialect, self,
                              **kwargs).traverse_single(element)


class GinoEngine:
    connection_cls = GinoConnection

    def __init__(self, dialect, pool, loop, logging_name=None, echo=None):
        self._sa_engine = SAEngine(dialect,
                                   logging_name=logging_name, echo=echo)
        self._dialect = dialect
        self._pool = pool
        self._loop = loop
        self._ctx = _get_context_var()('gino')

    @property
    def dialect(self):
        return self._dialect

    @property
    def raw_pool(self):
        return self._pool.raw_pool

    def acquire(self, *, timeout=None, reuse=False, lazy=False, reusable=True):
        return AcquireContext(functools.partial(
            self._acquire, timeout, reuse, lazy, reusable), self.release)

    async def _acquire(self, timeout, reuse, lazy, reusable):
        try:
            stack = self._ctx.get()
        except LookupError:
            stack = collections.deque()
            self._ctx.set(stack)
        if reuse and stack:
            dbapi_conn = ReusingDBAPIConnection(self._dialect.cursor_cls,
                                                stack[-1])
            reusable = False
        else:
            dbapi_conn = DBAPIConnection(self._dialect.cursor_cls, self._pool)
        rv = self.connection_cls(self._dialect,
                                 SAConnection(self._sa_engine, dbapi_conn),
                                 stack if reusable else None)
        dbapi_conn.gino_conn = rv
        if not lazy:
            await dbapi_conn.acquire(timeout=timeout)
        if reusable:
            stack.append(dbapi_conn)
        return rv

    async def release(self, connection):
        await connection.release(permanent=True)

    @property
    def current_connection(self):
        try:
            return self._ctx.get()[-1].gino_conn
        except (LookupError, IndexError):
            pass

    async def close(self):
        await self._pool.close()

    async def all(self, clause, *multiparams, **params):
        async with self.acquire(reuse=True) as conn:
            return await conn.all(clause, *multiparams, **params)

    async def first(self, clause, *multiparams, **params):
        async with self.acquire(reuse=True) as conn:
            return await conn.first(clause, *multiparams, **params)

    async def scalar(self, clause, *multiparams, **params):
        async with self.acquire(reuse=True) as conn:
            return await conn.scalar(clause, *multiparams, **params)

    async def status(self, clause, *multiparams, **params):
        async with self.acquire(reuse=True) as conn:
            return await conn.status(clause, *multiparams, **params)

    def compile(self, clause, *multiparams, **params):
        return self._dialect.compile(clause, *multiparams, **params)

    def transaction(self, *args, timeout=None, reuse=True, **kwargs):
        return TransactionContext(self.acquire(timeout=timeout, reuse=reuse),
                                  (args, kwargs))

    def iterate(self, clause, *multiparams, **params):
        connection = self.current_connection
        if connection is None:
            raise ValueError(
                'No Connection in context, please provide one')
        return connection.iterate(clause, *multiparams, **params)

    def update_execution_options(self, **opt):
        self._sa_engine.update_execution_options(**opt)

    async def _run_visitor(self, *args, **kwargs):
        async with self.acquire(reuse=True) as conn:
            await getattr(conn, '_run_visitor')(*args, **kwargs)
