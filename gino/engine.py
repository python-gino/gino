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


class _BaseDBAPIConnection:
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


class _DBAPIConnection(_BaseDBAPIConnection):
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


class _ReusingDBAPIConnection(_BaseDBAPIConnection):
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
class _SAConnection(Connection):
    pass


# noinspection PyAbstractClass
class _SAEngine(Engine):
    _connection_cls = _SAConnection

    def __init__(self, dialect, **kwargs):
        super().__init__(None, dialect, None, **kwargs)


class _AcquireContext:
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


class _TransactionContext:
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
    """
    Represents an actual database connection.

    This is the root of all query API like :meth:`all`, :meth:`first`,
    :meth:`scalar` or :meth:`status`, those on engine or query are simply
    wrappers of methods in this class.

    Usually instances of this class are created by :meth:`.GinoEngine.acquire`.

    .. note::

        :class:`.GinoConnection` may refer to zero or one underlying database
        connection - when a :class:`.GinoConnection` is acquired with
        ``lazy=True``, the underlying connection may still be in the pool,
        until a query API is called or :meth:`get_raw_connection` is called.

        Oppositely, one underlying database connection can be shared by many
        :class:`.GinoConnection` instances when they are acquired with
        ``reuse=True``. The actual database connection is only returned to the
        pool when the **root** :class:`.GinoConnection` is released. Read more
        in :meth:`GinoEngine.acquire` method.

    """

    # noinspection PyProtectedMember
    schema_for_object = schema._schema_getter(None)
    """A SQLAlchemy compatibility attribute, don't use it for now, it bites."""

    def __init__(self, dialect, sa_conn, stack=None):
        self._dialect = dialect
        self._sa_conn = sa_conn
        self._stack = stack

    @property
    def _dbapi_conn(self):
        return self._sa_conn.connection

    @property
    def raw_connection(self):
        """
        The current underlying database connection instance, type depends on
        the dialect in use. May be ``None`` if self is a lazy connection.

        """
        return self._dbapi_conn.raw_connection

    async def get_raw_connection(self, *, timeout=None):
        """
        Get the underlying database connection, acquire one if none present.

        :param timeout: Seconds to wait for the underlying acquiring
        :return: Underlying database connection instance depending on the
                 dialect in use
        :raises: :class:`~asyncio.TimeoutError` if the acquiring timed out

        """
        return await self._dbapi_conn.acquire(timeout=timeout)

    async def release(self, *, permanent=False):
        """
        Returns the underlying database connection to its pool.

        If ``permanent=False`` (default), this connection will be set in lazy
        mode with underlying database connection returned, the next query on
        this connection will cause a new database connection acquired. This is
        useful when this connection may still be useful again later, while some
        long-running I/O operations are about to take place, which should not
        take up one database connection or even transaction for that long time.

        Otherwise, this connection will be marked as closed after returning to
        pool, and be no longer usable again. ``permanent=True`` is the same as
        :meth:`.GinoEngine.release`.

        """
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
        """
        The :class:`~sqlalchemy.engine.interfaces.Dialect` in use, inherited
        from the engine created this connection.

        """
        return self._dialect

    def _execute(self, clause, multiparams, params):
        return self._sa_conn.execute(clause, *multiparams, **params)

    async def all(self, clause, *multiparams, **params):
        """
        Runs the given query in database, returns all results as a list.

        This method accepts the same parameters taken by SQLAlchemy
        :meth:`~sqlalchemy.engine.Connectable.execute`. You can pass in a raw
        SQL string, or *any* SQLAlchemy query clauses.

        If the given query clause is built by CRUD models, then the returning
        rows will be turned into relevant model objects (Only one type of model
        per query is supported for now, no relationship support yet). See
        :meth:`execution_options` for more information.

        If the given parameters are parsed as "executemany" - bulk inserting
        multiple rows in one call for example, the returning result from
        database will be discarded and this method will return ``None``.

        """
        result = self._execute(clause, multiparams, params)
        return await result.execute()

    async def first(self, clause, *multiparams, **params):
        """
        Runs the given query in database, returns the first result.

        If the query returns no result, this method will return ``None``.

        See :meth:`all` for common query comments.

        """
        result = self._execute(clause, multiparams, params)
        return await result.execute(one=True)

    async def scalar(self, clause, *multiparams, **params):
        """
        Runs the given query in database, returns the first result.

        If the query returns no result, this method will return ``None``.

        See :meth:`all` for common query comments.

        """
        result = self._execute(clause, multiparams, params)
        rv = await result.execute(one=True, return_model=False)
        if rv:
            return rv[0]
        else:
            return None

    async def status(self, clause, *multiparams, **params):
        """
        Runs the given query in database, returns the query status.

        The returning query status depends on underlying database and the
        dialect in use. For asyncpg it is a string, you can parse it like this:
        https://git.io/v7oze

        """
        result = self._execute(clause, multiparams, params)
        return await result.execute(status=True)

    def transaction(self, *args, **kwargs):
        """
        Starts a database transaction.

        There are two ways using this method: **managed** as an asynchronous
        context manager::

            async with conn.transaction() as tx:
                # run query in transaction

        or **manually** awaited::

            tx = await conn.transaction()
            try:
                # run query in transaction
                await tx.commit()
            except Exception:
                await tx.rollback()
                raise

        Where the ``tx`` is an instance of the
        :class:`~gino.transaction.GinoTransaction` class, feel free to read
        more about it.

        In the first managed mode, the transaction is automatically committed
        on exiting the context block, or rolled back if an exception was raised
        which led to the exit of the context. In the second manual mode, you'll
        need to manually call the
        :meth:`~gino.transaction.GinoTransaction.commit` or
        :meth:`~gino.transaction.GinoTransaction.rollback` methods on need.

        If this is a lazy connection, entering a transaction will cause a new
        database connection acquired if none was present.

        Transactions may support nesting depending on the dialect in use. For
        example in asyncpg, starting a second transaction on the same
        connection will create a save point in the database.

        For now, the parameters are directly passed to underlying database
        driver, read :meth:`asyncpg.connection.Connection.transaction` for
        asyncpg.

        """
        return GinoTransaction(self, args, kwargs)

    def iterate(self, clause, *multiparams, **params):
        """
        Creates a server-side cursor in database for large query results.

        Cursors must work within transactions::

            async with conn.transaction():
                async for user in conn.iterate(User.query):
                    # handle each user without loading all users into memory

        Alternatively, you can manually control how the cursor works::

            async with conn.transaction():
                cursor = await conn.iterate(User.query)
                user = await cursor.next()
                users = await cursor.many(10)

        Read more about how :class:`~gino.dialects.base.Cursor` works.

        Similarly, this method takes the same parameters as :meth:`all`.

        """
        result = self._execute(clause, multiparams, params)
        return result.iterate()

    def execution_options(self, **opt):
        """
        Set non-SQL options for the connection which take effect during
        execution.

        This method returns a copy of this :class:`.GinoConnection` which
        references the same underlying database connection, but with the given
        execution options set on the copy. Therefore, it is a good practice to
        discard the copy immediately after use, for example::

            row = await conn.execution_options(model=None).first(User.query)

        This is very much the same as SQLAlchemy
        :meth:`~sqlalchemy.engine.base.Connection.execution_options`, it
        actually does pass the execution options to the underlying SQLAlchemy
        :class:`~sqlalchemy.engine.base.Connection`. Furthermore, GINO added a
        few execution options:

        :param return_model: Boolean to control whether the returning results
          should be loaded into model instances, where the model class is
          defined in another execution option ``model``. Default is ``True``.

        :param model: Specifies the type of model instance to create on return.
          This has no effect if ``return_model`` is set to ``False``. Usually
          in queries built by CRUD models, this execution option is
          automatically set. For now, GINO only supports loading each row into
          one type of model object, relationships are not supported. Please use
          multiple queries for that. ``None`` for no postprocessing (default).

        :param timeout: Seconds to wait for the query to finish. ``None`` for
          no time out (default).

        """
        return type(self)(self._dialect,
                          self._sa_conn.execution_options(**opt))

    async def _run_visitor(self, visitorcallable, element, **kwargs):
        await visitorcallable(self.dialect, self,
                              **kwargs).traverse_single(element)


class GinoEngine:
    connection_cls = GinoConnection

    def __init__(self, dialect, pool, loop, logging_name=None, echo=None):
        self._sa_engine = _SAEngine(dialect,
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
        return _AcquireContext(functools.partial(
            self._acquire, timeout, reuse, lazy, reusable), self.release)

    async def _acquire(self, timeout, reuse, lazy, reusable):
        try:
            stack = self._ctx.get()
        except LookupError:
            stack = collections.deque()
            self._ctx.set(stack)
        if reuse and stack:
            dbapi_conn = _ReusingDBAPIConnection(self._dialect.cursor_cls,
                                                 stack[-1])
            reusable = False
        else:
            dbapi_conn = _DBAPIConnection(self._dialect.cursor_cls, self._pool)
        rv = self.connection_cls(self._dialect,
                                 _SAConnection(self._sa_engine, dbapi_conn),
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
        return _TransactionContext(self.acquire(timeout=timeout, reuse=reuse),
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
