from sqlalchemy.dialects.mysql.base import MySQLExecutionContext
from sqlalchemy.dialects.mysql.pymysql import MySQLDialect_pymysql

from .base import (
    AsyncCursor,
    AsyncDialectOverride,
    AsyncExecutionContextOverride,
    DBAPI,
)
from ..pool import AsyncPool


class AiomysqlDBAPI(DBAPI):
    paramstyle = "pyformat"

    def __init__(self):
        import aiomysql

        self.connect = aiomysql.connect


class AiomysqlCursor(AsyncCursor):
    cursor = None

    @property
    def description(self):
        return self.cursor.description

    async def execute(self, statement, parameters):
        cursor = self.cursor = await self.raw_conn.cursor()
        await cursor.execute(statement, parameters)

    async def fetchall(self):
        return await self.cursor.fetchall()


class MySQLExecutionContext_aiomysql(
    AsyncExecutionContextOverride, MySQLExecutionContext
):
    cursor_cls = AiomysqlCursor


class AiomysqlDialect(AsyncDialectOverride, MySQLDialect_pymysql):
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

    async def disconnect(self, conn):
        conn.close()
