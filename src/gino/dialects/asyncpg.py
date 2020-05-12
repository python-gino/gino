from sqlalchemy.dialects.postgresql.base import (
    PGCompiler,
    PGDialect,
    PGExecutionContext,
)

from .base import (
    AsyncCursor,
    AsyncDialectOverride,
    AsyncExecutionContextOverride,
    DBAPI,
)
from ..pool import AsyncPool


class AsyncpgDBAPI(DBAPI):
    def __init__(self):
        import asyncpg

        self.connect = asyncpg.connect


class AsyncpgBufferedCursor(AsyncCursor):
    description = None
    result = None
    status_msg = None

    async def execute(self, statement, parameters):
        with self.raw_conn._stmt_exclusive_section:
            result, stmt = await self.raw_conn._Connection__execute(
                statement, parameters, 0, None, True
            )
        self.description = [
            ((a[0], a[1][0]) + (None,) * 5) for a in stmt._get_attributes()
        ]
        self.result, self.status_msg = result[:2]

    async def fetchall(self):
        return self.result


class AsyncpgCompiler(PGCompiler):
    _bindtemplate = None

    @property
    def bindtemplate(self):
        return self._bindtemplate

    @bindtemplate.setter
    def bindtemplate(self, val):
        self._bindtemplate = val.replace(":", "$")

    def _apply_numbered_params(self):
        if hasattr(self, "string"):
            return super()._apply_numbered_params()


class PGExecutionContext_asyncpg(AsyncExecutionContextOverride, PGExecutionContext):
    cursor_cls = AsyncpgBufferedCursor


class AsyncpgDialect(AsyncDialectOverride, PGDialect):
    poolclass = AsyncPool
    execution_ctx_cls = PGExecutionContext_asyncpg
    statement_compiler = AsyncpgCompiler

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
