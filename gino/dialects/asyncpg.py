import weakref

import asyncpg
from asyncpg.prepared_stmt import PreparedStatement
# noinspection PyProtectedMember
from sqlalchemy.engine.util import _distill_params
from asyncpg.connection import Connection
from sqlalchemy import util
from sqlalchemy.dialects import registry
from sqlalchemy.events import PoolEvents
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.dialects.postgresql.base import (
    PGCompiler,
    PGDialect,
    PGExecutionContext,
)
from .pool import LazyConnection

from .base import (
    Pool, AsyncDialectMixin, DBAPIAdaptor, DBAPIConnectionAdaptor,
    ExecutionContextMixin,
)

DEFAULT = object()


class AsyncpgAdaptor(DBAPIConnectionAdaptor):
    def __init__(self, conn):
        super().__init__(conn)
        self._stmt = None

    async def prepare(self, statement):
        self._stmt = await self._conn.prepare(statement)

    async def first(self, *params):
        return await self._stmt.fetchrow(*params)

    async def scalar(self, *params):
        return await self._stmt.fetchval(*params)

    async def all(self, *params):
        return await self._stmt.fetch(*params)

    def get_description(self):
        try:
            return [((a[0], a[1][0]) + (None,) * 5)
                    for a in self._stmt.get_attributes()]
        except TypeError:  # asyncpg <= 0.12.0
            return []


class AsyncpgPool(Pool):
    adaptor = AsyncpgAdaptor

    def __init__(self, creator,
                 dialect=None,
                 loop=None,
                 min_size=10,
                 max_size=10,
                 max_queries=50000,
                 max_inactive_connection_lifetime=300.0,
                 setup=None,
                 init=None,
                 connection_class=Connection,
                 connect_kwargs=None):
        super().__init__(creator, dialect, loop)
        self._kwargs.update(
            min_size=min_size,
            max_size=max_size,
            max_queries=max_queries,
            max_inactive_connection_lifetime=max_inactive_connection_lifetime,
            setup=setup,
            init=init,
            connection_class=connection_class,
            **({} if connect_kwargs is None else connect_kwargs),
        )
        self._pool = None

    async def _init(self):
        self._pool = await asyncpg.create_pool(*self._args, **self._kwargs)

    async def _acquire(self):
        return await self._pool.acquire()

    async def _release(self, conn):
        return await self._pool.release(conn)


class AsyncpgCompiler(PGCompiler):
    @property
    def bindtemplate(self):
        return self._bindtemplate

    @bindtemplate.setter
    def bindtemplate(self, val):
        # noinspection PyAttributeOutsideInit
        self._bindtemplate = val.replace(':', '$')


class AnonymousPreparedStatement(PreparedStatement):
    def __del__(self):
        self._state.detach()


class ConnectionAdaptor:
    __slots__ = ('_dialect', '_conn', '_opts', '_stmt', '_echo')

    def __init__(self, dialect, connection, compiled_sql):
        self._dialect = dialect
        self._conn = connection
        self._opts = dict(getattr(connection, 'execution_options', {}))
        for opt in ('return_model', 'model', 'timeout'):
            if opt in compiled_sql.execution_options:
                self._opts.pop(opt, None)
        self._stmt = None
        self._echo = False

    def cursor(self):
        return self

    @property
    def dialect(self):
        return self._dialect

    @property
    def _execution_options(self):
        return self._opts

    @property
    def description(self):
        try:
            return [((a[0], a[1][0]) + (None,) * 5)
                    for a in self._stmt.get_attributes()]
        except TypeError:  # asyncpg <= 0.12.0
            return []

    def _branch(self):
        return self

    async def prepare(self, statement, named=True):
        if named:
            rv = await self._conn.prepare(statement)
        else:
            # it may still be a named statement, if cache is not disabled
            # noinspection PyProtectedMember
            self._conn._check_open()
            # noinspection PyProtectedMember
            state = await self._conn._get_statement(statement, None)
            if state.name:
                rv = PreparedStatement(self._conn, statement, state)
            else:
                rv = AnonymousPreparedStatement(self._conn, statement, state)
        self._stmt = rv
        return rv


class GinoCursorFactory:
    def __init__(self, env_factory, clause, multiparams, params):
        self._env_factory = env_factory
        self._context = None
        self._timeout = None
        self._clause = clause
        self._multiparams = multiparams
        self._params = params

    @property
    def timeout(self):
        return self._timeout

    async def get_cursor_factory(self):
        connection, metadata = self._env_factory()
        self._context = metadata.dialect.execution_ctx_cls.init_clause(
            metadata.dialect, self._clause, self._multiparams, self._params,
            connection)
        if self._context.executemany:
            raise ValueError('too many multiparams')
        self._timeout = self._context.timeout
        ps = await self._context.prepare()
        return ps.cursor(*self._context.parameters[0], timeout=self._timeout)

    @property
    def context(self):
        return self._context

    def __aiter__(self):
        return GinoCursorIterator(self)

    def __await__(self):
        return GinoCursor(self).async_init().__await__()


class GinoCursorIterator:
    def __init__(self, factory):
        self._factory = factory
        self._iterator = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._iterator is None:
            factory = await self._factory.get_cursor_factory()
            self._iterator = factory.__aiter__()
        row = await self._iterator.__anext__()
        return self._factory.context.process_rows([row])[0]


class GinoCursor:
    def __init__(self, factory):
        self._factory = factory
        self._cursor = None

    async def async_init(self):
        factory = await self._factory.get_cursor_factory()
        self._cursor = await factory
        return self

    async def many(self, n, *, timeout=DEFAULT):
        if timeout is DEFAULT:
            timeout = self._factory.timeout
        rows = await self._cursor.fetch(n, timeout=timeout)
        return self._factory.context.process_rows(rows)

    async def next(self, *, timeout=DEFAULT):
        if timeout is DEFAULT:
            timeout = self._factory.timeout
        row = await self._cursor.fetchrow(timeout=timeout)
        return self._factory.context.process_rows([row])[0]

    def __getattr__(self, item):
        return getattr(self._cursor, item)


class AsyncpgDBAPI(DBAPIAdaptor):
    Error = asyncpg.PostgresError, asyncpg.InterfaceError


# noinspection PyAbstractClass
class AsyncpgExecutionContext(PGExecutionContext, ExecutionContextMixin):
    @util.memoized_property
    def timeout(self):
        # noinspection PyUnresolvedReferences
        return self.execution_options.get('timeout', None)


# noinspection PyAbstractClass
class AsyncpgDialect(PGDialect, AsyncDialectMixin):
    driver = 'asyncpg'
    supports_native_decimal = True
    statement_compiler = AsyncpgCompiler
    execution_ctx_cls = AsyncpgExecutionContext
    poolclass = AsyncpgPool
    dbapi_class = AsyncpgDBAPI
    dbapi_type_map = {
        114: JSON(),
        3802: JSONB(),
    }

    def compile(self, elem, *multiparams, **params):
        context = self.execution_ctx_cls.init_clause(
            self, elem, multiparams, params, None)
        if context.executemany:
            return context.statement, context.parameters
        else:
            return context.statement, context.parameters[0]

    async def _execute_clauseelement(self, connection, clause, multiparams,
                                     params, many=False, status=False,
                                     return_model=True):
        context = self.execution_ctx_cls.init_clause(
            self, clause, multiparams, params, connection)
        if context.executemany and not many:
            raise ValueError('too many multiparams')
        # noinspection PyProtectedMember
        if isinstance(connection, LazyConnection):
            await connection.get_connection()
        with connection._stmt_exclusive_section:
            prepared = await context.prepare(named=False)
            rv = []
            for args in context.parameters:
                rows = await prepared.fetch(*args, timeout=context.timeout)
                item = context.process_rows(rows, return_model=return_model)
                if status:
                    item = prepared.get_statusmsg(), item
                if not many:
                    return item
                rv.append(item)
            return rv

    async def do_all(self, connection, clause, *multiparams, **params):
        return await self._execute_clauseelement(
            connection, clause, multiparams, params)

    async def do_first(self, connection, clause, *multiparams, **params):
        items = await self._execute_clauseelement(
            connection, clause, multiparams, params)
        if not items:
            return None
        return items[0]

    async def do_scalar(self, connection, clause, *multiparams, **params):
        items = await self._execute_clauseelement(
            connection, clause, multiparams, params, return_model=False)
        if not items:
            return None
        return items[0][0]

    async def do_status(self, connection, clause, *multiparams, **params):
        return (await self._execute_clauseelement(
            connection, clause, multiparams, params, status=True))[0]


for name in ('asyncpg', 'postgresql.asyncpg', 'postgres.asyncpg'):
    registry.register(name, 'gino.dialects.asyncpg', 'AsyncpgDialect')
# noinspection PyUnboundLocalVariable
del name
