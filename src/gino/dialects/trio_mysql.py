from typing import TYPE_CHECKING

from sqlalchemy.dialects.mysql.base import MySQLExecutionContext

from .aiomysql import AiomysqlDialect, AiomysqlCursor
from .base import DBAPI, AsyncExecutionContext

if TYPE_CHECKING:
    from trio_mysql.connections import Connection


class TrioMysqlDBAPI(DBAPI):
    paramstyle = "pyformat"

    def __init__(self):
        import trio_mysql
        from trio_mysql.cursors import Cursor, SSCursor

        for item in trio_mysql.__all__:
            setattr(self, item, getattr(trio_mysql, item))

        async def connect(*args, **kwargs):
            return await trio_mysql.connect(*args, **kwargs).__aenter__()

        self.connect = connect
        self.cursor_cls = Cursor
        self.ss_cursor_cls = SSCursor


class TrioMysqlCursor(AiomysqlCursor):
    if TYPE_CHECKING:
        raw_conn: Connection

    async def _make_cursor(self):
        return self.raw_conn.cursor(self.raw_cursor_cls)

    async def _close(self, cursor):
        await cursor.aclose()


class TrioMysqlSSCursor(TrioMysqlCursor):
    def __init__(self, dbapi: TrioMysqlDBAPI, raw_conn):
        super().__init__(dbapi, raw_conn)
        self.raw_cursor_cls = dbapi.ss_cursor_cls


class MySQLExecutionContext_trio_mysql(AsyncExecutionContext, MySQLExecutionContext):
    cursor_cls = TrioMysqlCursor
    server_side_cursor_cls = TrioMysqlSSCursor


class TrioMysqlDialect(AiomysqlDialect):
    execution_ctx_cls = MySQLExecutionContext_trio_mysql

    @classmethod
    def dbapi(cls):
        return TrioMysqlDBAPI()
