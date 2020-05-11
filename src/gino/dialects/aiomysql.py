from sqlalchemy.dialects.mysql.base import MySQLDialect, MySQLExecutionContext

from .base import AsyncResult, DBAPI
from ..pool import AsyncPool


class AiomysqlDBAPI(DBAPI):
    def __init__(self):
        import aiomysql

        self.connect = aiomysql.connect


class AiomysqlCursor:
    def __init__(self, raw_conn):
        self.raw_conn = raw_conn
        self.stmt = None
        self.cursor = None

    def __getattr__(self, item):
        return getattr(self.cursor, item)


class MySQLExecutionContext_aiomysql(MySQLExecutionContext):
    def create_cursor(self):
        return AiomysqlCursor(self._dbapi_connection)

    def _setup_result_proxy(self):
        result = AsyncResult(self)
        if self.compiled and not self.isddl and self.compiled.has_out_parameters:
            self._setup_out_parameters(result)
        return result


class AiomysqlDialect(MySQLDialect):
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

    async def do_execute(self, cursor, statement, parameters, context=None):
        cursor.cursor = await cursor.raw_conn.cursor()
        await cursor.cursor.execute(statement, *parameters)
