# TODO: This one needs porting

import inspect
import itertools
import time

import riopg
import psycopg2
import trio
from sqlalchemy import util, exc, sql
from sqlalchemy.dialects.postgresql import (  # noqa: F401
    ARRAY,
    CreateEnumType,
    DropEnumType,
    JSON,
    JSONB
)
from sqlalchemy.dialects.postgresql.base import (
    ENUM,
    PGCompiler,
    PGDialect,
    PGExecutionContext,
)
from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2, PGCompiler_psycopg2, PGExecutionContext_psycopg2
from sqlalchemy.engine.url import URL
from sqlalchemy.sql import sqltypes

from . import base


class RiopgDBAPI(base.BaseDBAPI):
    Error = psycopg2.Error


class RiopgCompiler(PGCompiler_psycopg2):
    pass


# noinspection PyAbstractClass
class RiopgExecutionContext(base.ExecutionContextOverride,
                            PGExecutionContext_psycopg2):

    async def _execute_scalar(self, stmt, type_):
        conn = self.root_connection
        if isinstance(stmt, util.text_type) and \
                not self.dialect.supports_unicode_statements:
            stmt = self.dialect._encoder(stmt)[0]

        if self.dialect.positional:
            default_params = self.dialect.execute_sequence_format()
        else:
            default_params = {}

        conn._cursor_execute(self.cursor, stmt, default_params, context=self)
        r = await self.cursor.async_execute(stmt, None, default_params, 1)
        r = r[0][0]
        if type_ is not None:
            # apply type post processors to the result
            proc = type_._cached_result_processor(
                self.dialect,
                self.cursor.description[0][1]
            )
            if proc:
                return proc(r)
        return r


class RiopgIterator:
    def __init__(self, context, iterator):
        self._context = context
        self._iterator = iterator

    async def __anext__(self):
        row = await self._iterator.__anext__()
        return self._context.process_rows([row])[0]


class RiopgCursor(base.Cursor):
    def __init__(self, context, cursor):
        self._context = context
        self._cursor = cursor

    async def many(self, n, *, timeout=base.DEFAULT):
        if timeout is base.DEFAULT:
            timeout = self._context.timeout
        rows = await self._cursor.fetch(n, timeout=timeout)
        return self._context.process_rows(rows)

    async def next(self, *, timeout=base.DEFAULT):
        if timeout is base.DEFAULT:
            timeout = self._context.timeout
        row = await self._cursor.fetchrow(timeout=timeout)
        if not row:
            return None
        return self._context.process_rows([row])[0]

    async def forward(self, n, *, timeout=base.DEFAULT):
        if timeout is base.DEFAULT:
            timeout = self._context.timeout
        await self._cursor.forward(n, timeout=timeout)


class PreparedStatement(base.PreparedStatement):
    def __init__(self, prepared, clause=None):
        super().__init__(clause)
        self._prepared = prepared

    def _get_iterator(self, *params, **kwargs):
        return RiopgIterator(
            self.context, self._prepared.cursor(*params, **kwargs).__aiter__())

    async def _get_cursor(self, *params, **kwargs):
        iterator = await self._prepared.cursor(*params, **kwargs)
        return RiopgCursor(self.context, iterator)

    async def _execute(self, params, one):
        if one:
            rv = await self._prepared.fetchrow(*params)
            if rv is None:
                rv = []
            else:
                rv = [rv]
        else:
            rv = await self._prepared.fetch(*params)
        return self._prepared.get_statusmsg(), rv


class DBAPICursor(base.DBAPICursor):
    def __init__(self, dbapi_conn):
        self._conn = dbapi_conn
        self._status = None

    async def prepare(self, context, clause=None):
        # XXX https://gist.github.com/dvarrazzo/3797445 ?
        timeout = context.timeout
        if timeout is None:
            conn = await self._conn.acquire(timeout=timeout)
        else:
            before = time.monotonic()
            conn = await self._conn.acquire(timeout=timeout)
            after = time.monotonic()
            timeout -= after - before
        prepared = await conn.prepare(context.statement, timeout=timeout)
        try:
            self._attributes = prepared.get_attributes()
        except TypeError:  # asyncpg <= 0.12.0
            self._attributes = []
        rv = PreparedStatement(prepared, clause)
        rv.context = context
        return rv

    async def async_execute(self, query, timeout, args, limit=0, many=False):
        if many:
            # ripog does not support this yet. Also psycopg2 just
            # uses a loop?
            # https://github.com/psycopg/psycopg2/issues/491
            raise RuntimeError('Not yet supported.')

        with trio.CancelScope() as scope:
            if timeout:
                scope.deadline = trio.current_time() + timeout

            conn = await self._conn.acquire()
            async with (await conn.cursor()) as cursor:
                await cursor.execute(query, args)
                if limit > 0:
                    result = await cursor.fetchall()
                else:
                    result = []

                self._description = cursor.description or []
                self._status = cursor.statusmessage
                return result

    @property
    def description(self):
        return self._description

    def get_statusmsg(self):
        return self._status


class Pool(base.Pool):
    def __init__(self, url, **kwargs):
        self._url = url
        self._kwargs = kwargs
        self._pool = None

    async def _init(self):
        args = self._kwargs.copy()
        # psycopg2 does not deal well with postgres+riopg urls.
        url = URL(
            drivername='postgres',
            username=self._url.username,
            password=self._url.password,
            database=self._url.database,
            host=self._url.host,
            port=self._url.port
        )
        args.update(
            dsn=str(url)
        )
        self._pool = await riopg.create_pool(**args)
        return self

    def __await__(self):
        return self._init().__await__()

    @property
    def raw_pool(self):
        return self._pool

    async def acquire(self, *, timeout=None):
        with trio.CancelScope() as scope:
            if timeout:
                scope.deadline = trio.current_time() + timeout
            return await self._pool.acquire()

    async def release(self, conn):
        await self._pool.release(conn)

    async def close(self):
        await self._pool.close()


class Transaction(base.Transaction):
    def __init__(self, conn):
        self._conn = conn

    async def begin(self):
        #await self._conn.start()
        pass

    async def commit(self):
        await self._conn.commit()

    async def rollback(self):
        await self._conn.rollback()


class AsyncEnum(ENUM):
    async def create_async(self, bind=None, checkfirst=True):
        if not checkfirst or \
            not await bind.dialect.has_type(
                bind, self.name, schema=self.schema):
            await bind.status(CreateEnumType(self))

    async def drop_async(self, bind=None, checkfirst=True):
        if not checkfirst or \
                await bind.dialect.has_type(bind, self.name,
                                            schema=self.schema):
            await bind.status(DropEnumType(self))

    async def _on_table_create_async(self, target, bind, checkfirst=False,
                                     **kw):
        if checkfirst or (
                not self.metadata and
                not kw.get('_is_metadata_operation', False)) and \
                not self._check_for_name_in_memos(checkfirst, kw):
            await self.create_async(bind=bind, checkfirst=checkfirst)

    async def _on_table_drop_async(self, target, bind, checkfirst=False, **kw):
        if not self.metadata and \
            not kw.get('_is_metadata_operation', False) and \
                not self._check_for_name_in_memos(checkfirst, kw):
            await self.drop_async(bind=bind, checkfirst=checkfirst)

    async def _on_metadata_create_async(self, target, bind, checkfirst=False,
                                        **kw):
        if not self._check_for_name_in_memos(checkfirst, kw):
            await self.create_async(bind=bind, checkfirst=checkfirst)

    async def _on_metadata_drop_async(self, target, bind, checkfirst=False,
                                      **kw):
        if not self._check_for_name_in_memos(checkfirst, kw):
            await self.drop_async(bind=bind, checkfirst=checkfirst)


# noinspection PyAbstractClass
class RiopgDialect(PGDialect_psycopg2, base.AsyncDialectMixin):
    driver = 'riopg'
    dbapi_class = RiopgDBAPI
    statement_compiler = RiopgCompiler
    execution_ctx_cls = RiopgExecutionContext
    cursor_cls = DBAPICursor
    init_kwargs = set()

    # init_kwargs = set(itertools.chain(
    #     *[inspect.getfullargspec(f).kwonlydefaults.keys() for f in
    #       [riopg.create_pool, riopg.Connection.open]]))
    colspecs = util.update_copy(
        PGDialect.colspecs,
        {
            ENUM: AsyncEnum,
            sqltypes.Enum: AsyncEnum,
        }
    )

    def __init__(self, *args, **kwargs):
        self._pool_kwargs = {}
        for k in self.init_kwargs:
            if k in kwargs:
                self._pool_kwargs[k] = kwargs.pop(k)
        super().__init__(*args, **kwargs)
        self._init_mixin()

    async def init_pool(self, url, loop, pool_class=None):
        # XXX: riopg supports a connection_factory argument we might be able to use.
        #init = self.on_connect()
        if pool_class is None:
            pool_class = Pool
        return await pool_class(url, **self._pool_kwargs)

    # noinspection PyMethodMayBeStatic
    def transaction(self, raw_conn, args, kwargs):
        return Transaction(raw_conn)

    def on_connect(self):
        if self.isolation_level is not None:
            async def connect(conn):
                await self.set_isolation_level(conn, self.isolation_level)
            return connect
        else:
            return None

    async def set_isolation_level(self, connection, level):
        """
        Given an asyncpg connection, set its isolation level.

        """
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
        """
        Given an asyncpg connection, return its isolation level.

        """
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
