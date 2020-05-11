from sqlalchemy.dialects.postgresql.base import PGDialect, PGExecutionContext

from .base import DBAPI, AsyncResult
from ..pool import AsyncPool


class AsyncpgDBAPI(DBAPI):
    def __init__(self):
        import asyncpg

        self.connect = asyncpg.connect


class AsyncpgCursor:
    def __init__(self, raw_conn):
        self.raw_conn = raw_conn
        self.description = None
        self.stmt = None

    def set_stmt(self, stmt):
        self.stmt = stmt
        self.description = [
            ((a[0], a[1][0]) + (None,) * 5) for a in stmt.get_attributes()
        ]

    async def fetchall(self):
        return await self.stmt.fetch()


class PGExecutionContext_asyncpg(PGExecutionContext):
    def create_cursor(self):
        return AsyncpgCursor(self._dbapi_connection)

    def _setup_result_proxy(self):
        result = AsyncResult(self)
        if self.compiled and not self.isddl and self.compiled.has_out_parameters:
            self._setup_out_parameters(result)
        return result


class AsyncpgDialect(PGDialect):
    poolclass = AsyncPool
    execution_ctx_cls = PGExecutionContext_asyncpg

    @classmethod
    def dbapi(cls):
        return AsyncpgDBAPI()

    def create_connect_args(self, url):
        opts = {}
        translate = dict(user="username")
        for name in ("host", "port", "user", "password", "database"):
            value = getattr(url, translate.get(name, name))
            if value is not None:
                opts[name] = value
        return (), opts

    async def do_begin(self, dbapi_connection):
        rv = dbapi_connection.transaction()
        await rv.start()
        return rv

    async def do_commit(self, tx):
        await tx.commit()

    async def do_rollback(self, tx):
        await tx.rollback()

    async def disconnect(self, conn):
        await conn.close()

    async def do_execute(self, cursor, statement, parameters, context=None):
        cursor.set_stmt(await cursor.raw_conn.prepare(statement, *parameters))
