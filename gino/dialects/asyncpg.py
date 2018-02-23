import inspect
import weakref

import asyncpg
from asyncpg.prepared_stmt import PreparedStatement
from sqlalchemy import util, exc
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.dialects.postgresql.base import (
    PGCompiler,
    PGDialect,
    PGExecutionContext,
)

DEFAULT = object()


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


# noinspection PyAbstractClass
class AsyncpgExecutionContext(PGExecutionContext):
    @util.memoized_property
    def return_model(self):
        # noinspection PyUnresolvedReferences
        return self.execution_options.get('return_model', True)

    @util.memoized_property
    def model(self):
        # noinspection PyUnresolvedReferences
        rv = self.execution_options.get('model', None)
        if isinstance(rv, weakref.ref):
            rv = rv()
        return rv

    @util.memoized_property
    def timeout(self):
        # noinspection PyUnresolvedReferences
        return self.execution_options.get('timeout', None)

    def process_rows(self, rows, return_model=True):
        rv = rows = super().get_result_proxy().process_rows(rows)
        if self.model is not None and return_model and self.return_model:
            rv = []
            for row in rows:
                obj = self.model()
                obj.__values__.update(row)
                rv.append(obj)
        return rv

    async def prepare(self, named=True):
        return await self.connection.prepare(self.statement, named)

    def get_result_proxy(self):
        return ResultProxy(self)


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


class Cursor:
    def __init__(self, apg_conn):
        self._conn = apg_conn
        self._stmt = None

    def execute(self, statement, parameters):
        pass

    @property
    def stmt_exclusive_section(self):
        return getattr(self._conn, '_stmt_exclusive_section')

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

    @property
    def description(self):
        try:
            return [((a[0], a[1][0]) + (None,) * 5)
                    for a in self._stmt.get_attributes()]
        except TypeError:  # asyncpg <= 0.12.0
            return []


class ResultProxy:
    _metadata = True

    def __init__(self, context):
        self._context = context

    @property
    def context(self):
        return self._context

    async def execute(self, one=False, return_model=True, status=False):
        context = self._context
        cursor = context.cursor
        with cursor.stmt_exclusive_section:
            prepared = await cursor.prepare(context.statement, named=False)
            rv = []
            for args in context.parameters:
                if one:
                    row = await prepared.fetchrow(*args,
                                                  timeout=context.timeout)
                    if row:
                        rows = [row]
                    else:
                        rows = []
                else:
                    rows = await prepared.fetch(*args, timeout=context.timeout)
                item = context.process_rows(rows, return_model=return_model)
                if status:
                    item = prepared.get_statusmsg(), item
                if not context.executemany:
                    return item
                rv.append(item)
            return rv


# noinspection PyAbstractClass
class AsyncpgDialect(PGDialect):
    driver = 'asyncpg'
    supports_native_decimal = True
    default_paramstyle = 'numeric'
    statement_compiler = AsyncpgCompiler
    execution_ctx_cls = AsyncpgExecutionContext
    cursor_cls = Cursor
    dbapi_type_map = {
        114: JSON(),
        3802: JSONB(),
    }

    def __init__(self, loop, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pool = None
        self._loop = loop
        from ..engine import SAConnection, SAEngine, DBAPIConnection
        self._sa_conn = SAConnection(SAEngine(self),
                                     DBAPIConnection(self, None))

    async def init_pool(self, url):
        formatters = {}
        kw = inspect.getfullargspec(asyncpg.create_pool).kwonlydefaults.copy()
        kw.update(inspect.getfullargspec(asyncpg.connect).kwonlydefaults)
        for key, val in kw.items():
            formatter = type(val)
            if formatter in {int, float}:
                formatters[key] = formatter
        query = {}
        for key, val in url.query.items():
            formatter = formatters.get(key, lambda x: x)
            query[key] = formatter(val)
        # noinspection PyAttributeOutsideInit
        self._pool = await asyncpg.create_pool(
            host=url.host,
            port=url.port,
            user=url.username,
            database=url.database,
            password=url.password,
            loop=self._loop,
            init=self.on_connect(),
            **query,
        )

    async def acquire_conn(self, *, timeout=None):
        return await self._pool.acquire(timeout=timeout)

    async def release_conn(self, conn):
        await self._pool.release(conn)

    async def close_pool(self):
        await self._pool.close()

    def compile(self, elem, *multiparams, **params):
        context = self._sa_conn.execute(elem, *multiparams, **params).context
        if context.executemany:
            return context.statement, context.parameters
        else:
            return context.statement, context.parameters[0]

    # noinspection PyMethodMayBeStatic
    def transaction(self, raw_conn, args, kwargs):
        return raw_conn.transaction(*args, **kwargs)

    def on_connect(self):
        if self.isolation_level is not None:
            async def connect(conn):
                await self.set_isolation_level(conn, self.isolation_level)
            return connect
        else:
            return None

    async def set_isolation_level(self, connection, level):
        level = level.replace('_', ' ')
        if level not in self._isolation_lookup:
            raise exc.ArgumentError(
                "Invalid value '%s' for isolation_level. "
                "Valid isolation levels for %s are %s" %
                (level, self.name, ", ".join(self._isolation_lookup))
            )
        await connection.execute(
            "SET SESSION CHARACTERISTICS AS TRANSACTION "
            "ISOLATION LEVEL %s" % level)
        await connection.execute("COMMIT")

    async def get_isolation_level(self, connection):
        val = await connection.fetchval('show transaction isolation level')
        return val.upper()
