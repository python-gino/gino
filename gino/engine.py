import collections
import functools

from sqlalchemy.engine import Engine, Connection
from sqlalchemy import exc

try:
    # noinspection PyPackageRequirements
    from contextvars import ContextVar
except ImportError:
    try:
        # noinspection PyPackageRequirements,PyUnresolvedReferences
        from aiocontextvars import ContextVar, enable_inherit
        enable_inherit()
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


class DBAPIConnection:
    _reset_agent = None

    def __init__(self, dialect, raw_conn):
        self._dialect = dialect
        self._raw_conn = raw_conn

    def cursor(self):
        return self._dialect.cursor_cls(self._raw_conn)

    def commit(self):
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
    def __init__(self, acquire):
        self._method = acquire

    async def __aenter__(self):
        method, self._method = self._method, None
        self._method, rv = await method()
        return rv

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        method, self._method = self._method, None
        if method is not None:
            await method()


class GinoEngine:
    def __init__(self, dialect, loop, logging_name=None, echo=None):
        self._sa_engine = SAEngine(dialect,
                                   logging_name=logging_name, echo=echo)
        self._dialect = dialect
        self._loop = loop
        self._ctx = ContextVar('gino')

    def acquire(self, *, timeout=None, reuse=False):
        return AcquireContext(functools.partial(self._acquire, timeout, reuse))

    async def _acquire(self, timeout, reuse):
        try:
            stack = self._ctx.get()
        except LookupError:
            stack = collections.deque()
            self._ctx.set(stack)
        if reuse and stack:
            return None, stack[-1]
        raw_conn = await self._dialect.acquire_conn(timeout=timeout)
        rv = GinoConnection(self._dialect, raw_conn, SAConnection(
            self._sa_engine, DBAPIConnection(self._dialect, raw_conn)))
        stack.append(rv)
        return functools.partial(self._release, stack), rv

    async def _release(self, stack):
        await self._dialect.release_conn(stack.pop().raw_connection)

    async def close(self):
        await self._dialect.close_pool()

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


class GinoConnection:
    def __init__(self, dialect, raw_conn, sa_conn):
        self._dialect = dialect
        self._raw_conn = raw_conn
        self._sa_conn = sa_conn

    @property
    def raw_connection(self):
        return self._raw_conn

    def _execute(self, clause, multiparams, params):
        return self._sa_conn.execute(clause, *multiparams, **params)

    async def all(self, clause, *multiparams, **params):
        result = self._execute(clause, multiparams, params)
        return await result.execute()

    async def first(self, clause, *multiparams, **params):
        result = self._execute(clause, multiparams, params)
        rv = await result.execute(one=True)
        if rv:
            rv = rv[0]
        return rv

    async def scalar(self, clause, *multiparams, **params):
        result = self._execute(clause, multiparams, params)
        rv = await result.execute(one=True, return_model=False)
        if rv:
            rv = rv[0][0]
        return rv

    async def status(self, clause, *multiparams, **params):
        """
        You can parse the return value like this: https://git.io/v7oze
        """
        result = self._execute(clause, multiparams, params)
        return await result.execute(status=True)

    def compile(self, clause, *multiparams, **params):
        return self._dialect.compile(clause, *multiparams, **params)
