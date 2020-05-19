from typing import Optional, TYPE_CHECKING

from sqlalchemy.dialects.mysql.base import MySQLExecutionContext
from sqlalchemy.dialects.mysql.pymysql import MySQLDialect_pymysql

from .base import AsyncDialect, AsyncExecutionContext, DBAPI
from ..cursor import AsyncCursor
from ..pool import AsyncPool

if TYPE_CHECKING:
    from aiomysql import Connection


class AiomysqlDBAPI(DBAPI):
    paramstyle = "pyformat"

    def __init__(self):
        import aiomysql

        for item in aiomysql.__all__:
            setattr(self, item, getattr(aiomysql, item))
        self.cursor_cls = aiomysql.Cursor
        self.ss_cursor_cls = aiomysql.SSCursor


class AiomysqlCursor(AsyncCursor):
    if TYPE_CHECKING:
        raw_conn: Connection

    def __init__(self, dbapi: AiomysqlDBAPI, raw_conn):
        super().__init__(dbapi, raw_conn)
        self.raw_cursor_cls = dbapi.cursor_cls
        self.raw_cursor = None

    async def _make_cursor(self):
        return await self.raw_conn.cursor(self.raw_cursor_cls)

    async def _execute_many(self, statement, parameters):
        cursor = await self._make_cursor()
        await cursor.executemany(statement, parameters)

    async def _execute_and_fetch(
        self, statement, parameters, *, limit: Optional[int] = None
    ):
        self.raw_cursor = await self._iterate(statement, parameters)
        if limit is None:
            return await self.raw_cursor.fetchall()
        elif limit == 1:
            return [await self.raw_cursor.fetchone()]
        else:
            return await self.raw_cursor.fetchmany(limit)

    async def _iterate(self, statement: str, parameters):
        cursor = await self._make_cursor()
        await cursor.execute(statement, parameters)
        self.description = cursor.description
        return cursor

    async def _fetchone(self):
        return await self.raw_cursor.fetchone()

    async def _fetchmany(self, size):
        return await self.raw_cursor.fetchmany(size)

    async def _fetchall(self):
        return await self.raw_cursor.fetchall()

    async def _close(self, cursor):
        await cursor.close()


class AiomysqlSSCursor(AiomysqlCursor):
    def __init__(self, dbapi: AiomysqlDBAPI, raw_conn):
        super().__init__(dbapi, raw_conn)
        self.raw_cursor_cls = dbapi.ss_cursor_cls


class MySQLExecutionContext_aiomysql(AsyncExecutionContext, MySQLExecutionContext):
    cursor_cls = AiomysqlCursor
    server_side_cursor_cls = AiomysqlSSCursor


class AiomysqlDialect(AsyncDialect, MySQLDialect_pymysql):
    poolclass = AsyncPool
    execution_ctx_cls = MySQLExecutionContext_aiomysql

    @classmethod
    def dbapi(cls):
        return AiomysqlDBAPI()

    def create_connect_args(self, url):
        opts = {}
        translate = dict(user="username", db="database")
        for name in ("host", "port", "user", "password", "db"):
            value = getattr(url, translate.get(name, name))
            if value is not None:
                opts[name] = value
        return (), opts

    async def do_begin(self, dbapi_connection):
        await dbapi_connection.begin()
        return dbapi_connection

    async def do_commit(self, dbapi_connection):
        await dbapi_connection.commit()

    async def do_rollback(self, dbapi_connection):
        await dbapi_connection.rollback()

    async def _disconnect(self, conn):
        conn.close()
