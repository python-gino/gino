import collections
import functools
import sys

from sqlalchemy.engine import Engine, Connection


def _get_context_var():
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
    return ContextVar


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
    __slots__ = ['_method']

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


class GinoEngine:
    def __init__(self, dialect, loop, logging_name=None, echo=None):
        self._sa_engine = SAEngine(dialect,
                                   logging_name=logging_name, echo=echo)
        self._dialect = dialect
        self._loop = loop
        self._ctx = _get_context_var()('gino')

    @property
    def dialect(self):
        return self._dialect

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

    @property
    def current_connection(self):
        try:
            return self._ctx.get()[-1]
        except (LookupError, IndexError):
            pass

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

    def transaction(self, *args, timeout=None, reuse=True, **kwargs):
        return TransactionContext(self.acquire(timeout=timeout, reuse=reuse),
                                  (args, kwargs))

    def update_execution_options(self, **opt):
        self._sa_engine.update_execution_options(**opt)


class _Break(Exception):
    def __init__(self, tx, commit):
        super().__init__()
        self.tx = tx
        self.commit = commit


class GinoTransaction:
    def __init__(self, conn, args, kwargs):
        self._conn = conn
        self._args = args
        self._kwargs = kwargs
        self._tx = None
        self._ctx = None
        self._managed = None

    async def _begin(self):
        self._ctx = self._conn.dialect.transaction(self._conn.raw_connection,
                                                   self._args, self._kwargs)
        self._tx = await self._ctx.__aenter__()
        return self

    @property
    def connection(self):
        return self._conn

    @property
    def transaction(self):
        return self._tx

    def raise_commit(self):
        raise _Break(self, True)

    async def commit(self):
        if self._managed:
            self.raise_commit()
        else:
            await self._ctx.__aexit__(None, None, None)

    def raise_rollback(self):
        raise _Break(self, False)

    async def rollback(self):
        if self._managed:
            self.raise_rollback()
        else:
            try:
                raise _Break(self, False)
            except _Break:
                await self._ctx.__aexit__(*sys.exc_info())

    def __await__(self):
        assert self._managed is None
        self._managed = False
        return self._begin().__await__()

    async def __aenter__(self):
        assert self._managed is None
        self._managed = True
        await self._begin()
        return self

    async def __aexit__(self, *exc_info):
        try:
            is_break = exc_info[0] is _Break
            ex = exc_info[1]
            if is_break and ex.commit:
                exc_info = None, None, None
        except Exception:
            exc_info = sys.exc_info()
            raise
        finally:
            await self._ctx.__aexit__(*exc_info)
        if is_break and ex.tx is self:
            return True


class GinoConnection:
    def __init__(self, dialect, raw_conn, sa_conn):
        self._dialect = dialect
        self._raw_conn = raw_conn
        self._sa_conn = sa_conn

    @property
    def raw_connection(self):
        return self._raw_conn

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
            if result.context.executemany:
                return [row[0] if row else None for row in rv]
            else:
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
        return GinoConnection(self._dialect, self._raw_conn,
                              self._sa_conn.execution_options(**opt))
