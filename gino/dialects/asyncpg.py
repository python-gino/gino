import inspect
import itertools
import weakref

import asyncpg
from sqlalchemy import util, exc, sql
from sqlalchemy.dialects.postgresql import *
from sqlalchemy.dialects.postgresql.base import (
    PGCompiler,
    PGDialect,
    PGExecutionContext,
)
from sqlalchemy.sql import sqltypes

from ..engine import SAConnection, SAEngine, DBAPIConnection

DEFAULT = object()


class AsyncpgCompiler(PGCompiler):
    @property
    def bindtemplate(self):
        return self._bindtemplate

    @bindtemplate.setter
    def bindtemplate(self, val):
        # noinspection PyAttributeOutsideInit
        self._bindtemplate = val.replace(':', '$')

    def _apply_numbered_params(self):
        if hasattr(self, 'string'):
            return super()._apply_numbered_params()


_NO_DEFAULT = object()


# noinspection PyAbstractClass
class AsyncpgExecutionContext(PGExecutionContext):
    def _compiled_first_opt(self, key, default=_NO_DEFAULT):
        rv = _NO_DEFAULT
        opts = getattr(getattr(self, 'compiled', None), 'execution_options',
                       None)
        if opts:
            rv = opts.get(key, _NO_DEFAULT)
        if rv is _NO_DEFAULT:
            # noinspection PyUnresolvedReferences
            rv = self.execution_options.get(key, default)
        if rv is _NO_DEFAULT:
            raise LookupError('No such execution option!')
        return rv

    @util.memoized_property
    def return_model(self):
        return self._compiled_first_opt('return_model', True)

    @util.memoized_property
    def model(self):
        rv = self._compiled_first_opt('model', None)
        if isinstance(rv, weakref.ref):
            rv = rv()
        return rv

    @util.memoized_property
    def timeout(self):
        return self._compiled_first_opt('timeout', None)

    def process_rows(self, rows, return_model=True):
        rv = rows = super().get_result_proxy().process_rows(rows)
        if self.model is not None and return_model and self.return_model:
            rv = []
            for row in rows:
                obj = self.model()
                obj.__values__.update(row)
                rv.append(obj)
        return rv

    def get_result_proxy(self):
        return ResultProxy(self)


class CursorFactory:
    def __init__(self, context):
        self._context = context

    @property
    def context(self):
        return self._context

    async def get_raw_cursor(self):
        prepared = await self._context.cursor.prepare(self._context.statement,
                                                      self._context.timeout)
        return prepared.cursor(*self._context.parameters[0],
                               timeout=self._context.timeout)

    def __aiter__(self):
        return CursorIterator(self)

    def __await__(self):
        return Cursor(self).async_init().__await__()


class CursorIterator:
    def __init__(self, factory):
        self._factory = factory
        self._iterator = None

    async def __anext__(self):
        if self._iterator is None:
            raw = await self._factory.get_raw_cursor()
            self._iterator = raw.__aiter__()
        row = await self._iterator.__anext__()
        return self._factory.context.process_rows([row])[0]


class Cursor:
    def __init__(self, factory):
        self._factory = factory
        self._cursor = None

    async def async_init(self):
        raw = await self._factory.get_raw_cursor()
        self._cursor = await raw
        return self

    async def many(self, n, *, timeout=DEFAULT):
        if timeout is DEFAULT:
            timeout = self._factory.context.timeout
        rows = await self._cursor.fetch(n, timeout=timeout)
        return self._factory.context.process_rows(rows)

    async def next(self, *, timeout=DEFAULT):
        if timeout is DEFAULT:
            timeout = self._factory.context.timeout
        row = await self._cursor.fetchrow(timeout=timeout)
        if not row:
            return None
        return self._factory.context.process_rows([row])[0]


class DBAPICursor:
    def __init__(self, apg_conn):
        self._conn = apg_conn
        self._attributes = None
        self._status = None

    def execute(self, statement, parameters):
        pass

    def executemany(self, statement, parameters):
        pass

    async def prepare(self, query, timeout):
        prepared = await self._conn.prepare(query, timeout=timeout)
        try:
            self._attributes = prepared.get_attributes()
        except TypeError:  # asyncpg <= 0.12.0
            self._attributes = []
        return prepared

    async def async_execute(self, query, timeout, args, limit=0, many=False):
        _protocol = getattr(self._conn, '_protocol')
        timeout = getattr(_protocol, '_get_timeout')(timeout)

        def executor(state, timeout_):
            if many:
                return _protocol.bind_execute_many(state, args, '', timeout_)
            else:
                return _protocol.bind_execute(state, args, '', limit, True,
                                              timeout_)

        with getattr(self._conn, '_stmt_exclusive_section'):
            result, stmt = await getattr(self._conn, '_do_execute')(
                query, executor, timeout)
            try:
                self._attributes = getattr(stmt, '_get_attributes')()
            except TypeError:  # asyncpg <= 0.12.0
                self._attributes = []
            if not many:
                result, self._status = result[:2]
            return result

    @property
    def description(self):
        return [((a[0], a[1][0]) + (None,) * 5) for a in self._attributes]

    def get_statusmsg(self):
        return self._status.decode()


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
        if context.executemany:
            return await cursor.async_execute(
                context.statement, context.timeout, context.parameters,
                many=True)
        else:
            args = context.parameters[0]
            rows = await cursor.async_execute(
                context.statement, context.timeout, args, 1 if one else 0)
            item = context.process_rows(rows, return_model=return_model)
            if one:
                if item:
                    item = item[0]
                else:
                    item = None
            if status:
                item = cursor.get_statusmsg(), item
            return item

    def iterate(self):
        if self._context.executemany:
            raise ValueError('too many multiparams')
        return CursorFactory(self._context)

    def _soft_close(self):
        pass


# noinspection PyAbstractClass
class AsyncpgDialect(PGDialect):
    driver = 'asyncpg'
    supports_native_decimal = True
    default_paramstyle = 'numeric'
    statement_compiler = AsyncpgCompiler
    execution_ctx_cls = AsyncpgExecutionContext
    cursor_cls = DBAPICursor
    dbapi_type_map = {
        114: JSON(),
        3802: JSONB(),
    }
    init_kwargs = set(itertools.chain(
        *[inspect.getfullargspec(f).kwonlydefaults.keys() for f in
          [asyncpg.create_pool, asyncpg.connect]]))

    def __init__(self, loop, *args, **kwargs):
        self._pool_kwargs = dict(loop=loop)
        for k in self.init_kwargs:
            if k in kwargs:
                self._pool_kwargs[k] = kwargs.pop(k)
        super().__init__(*args, **kwargs)
        self._pool = None
        self._sa_conn = SAConnection(SAEngine(self),
                                     DBAPIConnection(self, None))

    async def init_pool(self, url):
        args = self._pool_kwargs.copy()
        args.update(
            host=url.host,
            port=url.port,
            user=url.username,
            database=url.database,
            password=url.password,
            init=self.on_connect(),
        )
        self._pool = await asyncpg.create_pool(**args)

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

    async def has_schema(self, connection, schema):
        query = ("select nspname from pg_namespace "
                 "where lower(nspname)=:schema")
        row = await connection.first(
            sql.text(
                query,
                bindparams=[
                    sql.bindparam(
                        'schema', util.text_type(schema.lower()),
                        type_=sqltypes.Unicode)]
            )
        )

        return bool(row)

    async def has_table(self, connection, table_name, schema=None):
        # seems like case gets folded in pg_class...
        if schema is None:
            row = await connection.first(
                sql.text(
                    "select relname from pg_class c join pg_namespace n on "
                    "n.oid=c.relnamespace where "
                    "pg_catalog.pg_table_is_visible(c.oid) "
                    "and relname=:name",
                    bindparams=[
                        sql.bindparam('name', util.text_type(table_name),
                                      type_=sqltypes.Unicode)]
                )
            )
        else:
            row = await connection.first(
                sql.text(
                    "select relname from pg_class c join pg_namespace n on "
                    "n.oid=c.relnamespace where n.nspname=:schema and "
                    "relname=:name",
                    bindparams=[
                        sql.bindparam('name',
                                      util.text_type(table_name),
                                      type_=sqltypes.Unicode),
                        sql.bindparam('schema',
                                      util.text_type(schema),
                                      type_=sqltypes.Unicode)]
                )
            )
        return bool(row)

    async def has_sequence(self, connection, sequence_name, schema=None):
        if schema is None:
            row = await connection.first(
                sql.text(
                    "SELECT relname FROM pg_class c join pg_namespace n on "
                    "n.oid=c.relnamespace where relkind='S' and "
                    "n.nspname=current_schema() "
                    "and relname=:name",
                    bindparams=[
                        sql.bindparam('name', util.text_type(sequence_name),
                                      type_=sqltypes.Unicode)
                    ]
                )
            )
        else:
            row = await connection.first(
                sql.text(
                    "SELECT relname FROM pg_class c join pg_namespace n on "
                    "n.oid=c.relnamespace where relkind='S' and "
                    "n.nspname=:schema and relname=:name",
                    bindparams=[
                        sql.bindparam('name', util.text_type(sequence_name),
                                      type_=sqltypes.Unicode),
                        sql.bindparam('schema',
                                      util.text_type(schema),
                                      type_=sqltypes.Unicode)
                    ]
                )
            )

        return bool(row)

    async def has_type(self, connection, type_name, schema=None):
        if schema is not None:
            query = """
            SELECT EXISTS (
                SELECT * FROM pg_catalog.pg_type t, pg_catalog.pg_namespace n
                WHERE t.typnamespace = n.oid
                AND t.typname = :typname
                AND n.nspname = :nspname
                )
                """
            query = sql.text(query)
        else:
            query = """
            SELECT EXISTS (
                SELECT * FROM pg_catalog.pg_type t
                WHERE t.typname = :typname
                AND pg_type_is_visible(t.oid)
                )
                """
            query = sql.text(query)
        query = query.bindparams(
            sql.bindparam('typname',
                          util.text_type(type_name), type_=sqltypes.Unicode),
        )
        if schema is not None:
            query = query.bindparams(
                sql.bindparam('nspname',
                              util.text_type(schema), type_=sqltypes.Unicode),
            )
        return bool(await connection.scalar(query))
