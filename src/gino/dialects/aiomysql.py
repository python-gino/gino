import asyncio
import inspect
import itertools
import re
import time
import warnings

import aiomysql
from sqlalchemy import util, exc
from sqlalchemy.dialects.mysql import JSON, ENUM
from sqlalchemy.dialects.mysql.base import (
    MySQLCompiler,
    MySQLDialect,
    MySQLExecutionContext,
)
from sqlalchemy.sql import sqltypes

from . import base

try:
    import click
except ImportError:
    click = None
JSON_COLTYPE = 245

#: Regular expression for :meth:`Cursor.executemany`.
#: executemany only supports simple bulk insert.
#: You can use it to load large dataset.
_RE_INSERT_VALUES = re.compile(
    r"\s*((?:INSERT|REPLACE)\s.+\sVALUES?\s+)"
    + r"(\(\s*(?:%s|%\(.+\)s)\s*(?:,\s*(?:%s|%\(.+\)s)\s*)*\))"
    + r"(\s*(?:ON DUPLICATE.*)?);?\s*\Z",
    re.IGNORECASE | re.DOTALL,
)

#: Max statement size which :meth:`executemany` generates.
#:
#: Max size of allowed statement is max_allowed_packet -
# packet_header_size.
#: Default value of max_allowed_packet is 1048576.
_MAX_STMT_LENGTH = 1024000


class AiomysqlDBAPI(base.BaseDBAPI):
    paramstyle = "format"


# noinspection PyAbstractClass
class AiomysqlExecutionContext(base.ExecutionContextOverride, MySQLExecutionContext):
    def get_lastrowid(self):
        lastrowid = self.cursor.last_row_id
        return None if lastrowid == 0 else lastrowid

    def get_affected_rows(self):
        return self.cursor.affected_rows


class AiomysqlIterator(base.Cursor):
    def __init__(self, context, cursor):
        self._context = context
        self._cursor = cursor
        self._queried = False

    def __await__(self):
        async def return_self():
            return self

        return return_self().__await__()

    def __aiter__(self):
        return self

    async def _init(self):
        if not self._queried:
            query = self._context.statement
            args = self._context.parameters[0]
            await self._cursor.execute(query, args)
            self._context.cursor._cursor_description = self._cursor.description
            self._queried = True

    async def __anext__(self):
        await self._init()
        row = await asyncio.wait_for(self._cursor.fetchone(), self._context.timeout)
        if row is None:
            raise StopAsyncIteration
        return self._context.process_rows([row])[0]

    async def many(self, n, *, timeout=base.DEFAULT):
        await self._init()
        if timeout is base.DEFAULT:
            timeout = self._context.timeout
        rows = await asyncio.wait_for(self._cursor.fetchmany(n), timeout)
        if not rows:
            return []
        return self._context.process_rows(rows)

    async def next(self, *, timeout=base.DEFAULT):
        try:
            return await self.__anext__()
        except StopAsyncIteration:
            return None

    async def forward(self, n, *, timeout=base.DEFAULT):
        await self._init()
        if timeout is base.DEFAULT:
            timeout = self._context.timeout
        await asyncio.wait_for(self._cursor.scroll(n, mode="relative"), timeout)


class DBAPICursor(base.DBAPICursor):
    def __init__(self, dbapi_conn):
        self._conn = dbapi_conn
        self._cursor_description = None
        self._status = None
        self.last_row_id = None
        self.affected_rows = 0

    async def prepare(self, context, clause=None):
        raise Exception("aiomysql doesn't support prepare")

    async def async_execute(self, query, timeout, args, limit=0, many=False):
        if timeout is None:
            conn = await self._conn.acquire(timeout=timeout)
        else:
            before = time.monotonic()
            conn = await self._conn.acquire(timeout=timeout)
            after = time.monotonic()
            timeout -= after - before

        if not many:
            return await self._async_execute(conn, query, timeout, args)

        return await asyncio.wait_for(
            self._async_executemany(conn, query, args), timeout=timeout
        )

    async def execute_baked(self, baked_query, timeout, args, one):
        # TODO: use prepare when it's supported
        return await self.async_execute(baked_query.sql, timeout, args)

    async def _async_execute(self, conn, query, timeout, args):
        if args is not None:
            query = query % _escape_args(args, conn)
        await asyncio.wait_for(conn.query(query), timeout=timeout)
        # noinspection PyProtectedMember
        result = conn._result
        self._cursor_description = result.description
        self._status = result.affected_rows
        self.last_row_id = result.insert_id
        self.affected_rows = result.affected_rows
        return result.rows

    async def _async_executemany(self, conn, query, args):
        m = _RE_INSERT_VALUES.match(query)
        if m:
            q_prefix = m.group(1)
            q_values = m.group(2).rstrip()
            q_postfix = m.group(3) or ""
            return await self._do_execute_many(
                conn, q_prefix, q_values, q_postfix, args
            )
        else:
            rows = 0
            for arg in args:
                await self.execute(query, arg)
                rows += self.affected_rows
            self.affected_rows = rows
        return None

    async def _do_execute_many(self, conn, prefix, values, postfix, args):
        escape = _escape_args
        if isinstance(prefix, str):
            prefix = prefix.encode(conn.encoding)
        if isinstance(postfix, str):
            postfix = postfix.encode(conn.encoding)
        stmt = bytearray(prefix)
        args = iter(args)
        v = values % escape(next(args), conn)
        if isinstance(v, str):
            v = v.encode(conn.encoding, "surrogateescape")
        stmt += v
        rows = 0
        for arg in args:
            v = values % escape(arg, conn)
            if isinstance(v, str):
                v = v.encode(conn.encoding, "surrogateescape")
            if len(stmt) + len(v) + len(postfix) + 1 > _MAX_STMT_LENGTH:
                await self._async_execute(conn, stmt + postfix, None, None)
                rows += self.affected_rows
                stmt = bytearray(prefix)
            else:
                stmt += b","
            stmt += v
        await self._async_execute(conn, stmt + postfix, None, None)
        self.affected_rows += rows

    @property
    def description(self):
        return self._cursor_description

    def get_statusmsg(self):
        return self._status

    def iterate(self, context):
        # use SSCursor to get server side cursor
        return AiomysqlIterator(context, aiomysql.SSCursor(self._conn.raw_connection))


class Pool(base.Pool):
    def __init__(self, url, loop, init=None, bakery=None, prebake=True, **kwargs):
        self._url = url
        self._loop = loop
        self._kwargs = kwargs
        self._pool = None
        self._conn_init = init
        self._bakery = bakery
        self._prebake = prebake

    async def _init(self):
        args = self._kwargs.copy()
        args.update(
            loop=self._loop,
            host=self._url.host,
            port=self._url.port,
            user=self._url.username,
            db=self._url.database,
            password=self._url.password,
        )
        # aiomysql sets autocommit as False by default, which opposes the MySQL
        # default, therefore it's set to None to respect the MySQL configuration
        args.setdefault("autocommit", None)
        self._pool = await aiomysql.create_pool(**args)
        return self

    def __await__(self):
        return self._init().__await__()

    @property
    def raw_pool(self):
        return self._pool

    async def acquire(self, *, timeout=None):
        if timeout is None:
            conn = await self._pool.acquire()
        else:
            conn = await asyncio.wait_for(self._pool.acquire(), timeout=timeout)
        if self._conn_init is not None:
            try:
                await self._conn_init(conn)
            except:
                await self.release(conn)
                raise
        return conn

    async def release(self, conn):
        await self._pool.release(conn)

    async def close(self):
        self._pool.close()
        await self._pool.wait_closed()

    def repr(self, color):
        if color and not click:
            warnings.warn("Install click to get colorful repr.", ImportWarning)

        if color and click:
            # noinspection PyProtectedMember
            return "<{classname} max={max} min={min} cur={cur} use={use}>".format(
                classname=click.style(
                    self._pool.__class__.__module__
                    + "."
                    + self._pool.__class__.__name__,
                    fg="green",
                ),
                max=click.style(repr(self._pool.maxsize), fg="cyan"),
                min=click.style(repr(self._pool._minsize), fg="cyan"),
                cur=click.style(repr(self._pool.size), fg="cyan"),
                use=click.style(repr(len(self._pool._used)), fg="cyan"),
            )
        else:
            # noinspection PyProtectedMember
            return "<{classname} max={max} min={min} cur={cur} use={use}>".format(
                classname=self._pool.__class__.__module__
                + "."
                + self._pool.__class__.__name__,
                max=self._pool.maxsize,
                min=self._pool._minsize,
                cur=self._pool.size,
                use=len(self._pool._used),
            )


class Transaction(base.Transaction):
    def __init__(self, conn, set_isolation=None):
        self._conn = conn
        self._set_isolation = set_isolation

    @property
    def raw_transaction(self):
        return self._conn

    async def begin(self):
        await self._conn.begin()
        if self._set_isolation is not None:
            await self._set_isolation(self._conn)

    async def commit(self):
        await self._conn.commit()

    async def rollback(self):
        await self._conn.rollback()


# MySQL doesn't need to create ENUM types like PostgreSQL, do nothing here
class AsyncEnum(ENUM):
    async def create_async(self, bind=None, checkfirst=True):
        pass

    async def drop_async(self, bind=None, checkfirst=True):
        pass

    async def _on_table_create_async(self, target, bind, checkfirst=False, **kw):
        pass

    async def _on_table_drop_async(self, target, bind, checkfirst=False, **kw):
        pass

    async def _on_metadata_create_async(self, target, bind, checkfirst=False, **kw):
        pass

    async def _on_metadata_drop_async(self, target, bind, checkfirst=False, **kw):
        pass


class GinoNullType(sqltypes.NullType):
    def result_processor(self, dialect, coltype):
        if coltype == JSON_COLTYPE:
            return JSON().result_processor(dialect, coltype)
        return super().result_processor(dialect, coltype)


# noinspection PyAbstractClass
class AiomysqlDialect(MySQLDialect, base.AsyncDialectMixin):
    driver = "aiomysql"
    supports_native_decimal = True
    dbapi_class = AiomysqlDBAPI
    statement_compiler = MySQLCompiler
    execution_ctx_cls = AiomysqlExecutionContext
    cursor_cls = DBAPICursor
    init_kwargs = set(
        itertools.chain(
            ("bakery", "prebake"),
            *[
                inspect.getfullargspec(f).args
                for f in [aiomysql.create_pool, aiomysql.connect]
            ]
        )
    ) - {
        "echo"
    }  # use SQLAlchemy's echo instead
    colspecs = util.update_copy(
        MySQLDialect.colspecs,
        {ENUM: AsyncEnum, sqltypes.Enum: AsyncEnum, sqltypes.NullType: GinoNullType,},
    )
    postfetch_lastrowid = False
    support_returning = False
    support_prepare = False

    def __init__(self, *args, bakery=None, **kwargs):
        self._pool_kwargs = {}
        for k in self.init_kwargs:
            if k in kwargs:
                self._pool_kwargs[k] = kwargs.pop(k)
        super().__init__(*args, **kwargs)
        self._init_mixin(bakery)

    async def init_pool(self, url, loop, pool_class=None):
        if pool_class is None:
            pool_class = Pool
        return await pool_class(
            url, loop, bakery=self._bakery, init=self.on_connect(), **self._pool_kwargs
        )

    # noinspection PyMethodMayBeStatic
    def transaction(self, raw_conn, args, kwargs):
        _set_isolation = None
        if "isolation" in kwargs:

            async def _set_isolation(conn):
                await self.set_isolation_level(conn, kwargs["isolation"])

        return Transaction(raw_conn, _set_isolation)

    def on_connect(self):
        if self.isolation_level is not None:

            async def connect(conn):
                await self.set_isolation_level(conn, self.isolation_level)

            return connect
        else:
            return None

    async def set_isolation_level(self, connection, level):
        level = level.replace("_", " ")
        await self._set_isolation_level(connection, level)

    async def _set_isolation_level(self, connection, level):
        if level not in self._isolation_lookup:
            raise exc.ArgumentError(
                "Invalid value '%s' for isolation_level. "
                "Valid isolation levels for %s are %s"
                % (level, self.name, ", ".join(self._isolation_lookup))
            )
        cursor = await connection.cursor()
        await cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL %s" % level)
        await cursor.execute("COMMIT")
        await cursor.close()

    async def get_isolation_level(self, connection):
        if self.server_version_info is None:
            self.server_version_info = await self._get_server_version_info(connection)
        cursor = await connection.cursor()
        if self._is_mysql and self.server_version_info >= (5, 7, 20):
            await cursor.execute("SELECT @@transaction_isolation")
        else:
            await cursor.execute("SELECT @@tx_isolation")
        row = await cursor.fetchone()
        if row is None:
            util.warn(
                "Could not retrieve transaction isolation level for MySQL "
                "connection."
            )
            raise NotImplementedError()
        val = row[0]
        await cursor.close()
        if isinstance(val, bytes):
            val = val.decode()
        return val.upper().replace("-", " ")

    async def _get_server_version_info(self, connection):
        # get database server version info explicitly over the wire
        # to avoid proxy servers like MaxScale getting in the
        # way with their own values, see #4205
        cursor = await connection.cursor()
        await cursor.execute("SELECT VERSION()")
        val = (await cursor.fetchone())[0]
        await cursor.close()
        if isinstance(val, bytes):
            val = val.decode()

        return self._parse_server_version(val)

    def _parse_server_version(self, val):
        version = []
        r = re.compile(r"[.\-]")
        for n in r.split(val):
            try:
                version.append(int(n))
            except ValueError:
                mariadb = re.match(r"(.*)(MariaDB)(.*)", n)
                if mariadb:
                    version.extend(g for g in mariadb.groups() if g)
                else:
                    version.append(n)
        return tuple(version)

    async def has_table(self, connection, table_name, schema=None):
        full_name = ".".join(
            self.identifier_preparer._quote_free_identifiers(schema, table_name)
        )

        st = "DESCRIBE %s" % full_name
        try:
            return await connection.first(st) is not None
        except aiomysql.ProgrammingError as e:
            if self._extract_error_code(e) == 1146:
                return False
            raise

    def _extract_error_code(self, exception):
        if isinstance(exception.args[0], Exception):
            exception = exception.args[0]
        return exception.args[0]


def _escape_args(args, conn):
    if isinstance(args, (tuple, list)):
        return tuple(conn.escape(arg) for arg in args)
    elif isinstance(args, dict):
        return dict((key, conn.escape(val)) for (key, val) in args.items())
    else:
        # If it's not a dictionary let's try escaping it anyways.
        # Worst case it will throw a Value error
        return conn.escape(args)
