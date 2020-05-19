from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from sqlalchemy.dialects.postgresql.base import (
    PGCompiler,
    PGDialect,
    PGExecutionContext,
)

from .base import AsyncDialect, AsyncExecutionContext, DBAPI
from ..cursor import AsyncCursor
from ..pool import AsyncPool

if TYPE_CHECKING:
    from asyncpg import Connection
    from asyncpg.cursor import Cursor


class AsyncpgDBAPI(DBAPI):
    def __init__(self):
        import asyncpg

        self.connect = asyncpg.connect
        self.Error = asyncpg.PostgresError, asyncpg.InterfaceError


class AsyncpgCursor(AsyncCursor):
    if TYPE_CHECKING:
        raw_conn: Connection

    def __init__(self, dbapi, raw_conn):
        super().__init__(dbapi, raw_conn)
        self.status_msg = None
        self.execute_completed = False

    def set_attributes(self, attributes):
        self.description = [((a[0], a[1][0]) + (None,) * 5) for a in attributes]

    async def _execute_many(self, statement, parameters):
        await self.raw_conn.executemany(statement, parameters)

    async def _execute_and_fetch(
        self, statement, parameters, *, limit: Optional[int] = None
    ):
        with self.raw_conn._stmt_exclusive_section:
            result, stmt = await self.raw_conn._Connection__execute(
                statement, parameters, 0 if limit is None else limit, None, True
            )
        self.set_attributes(stmt._get_attributes())
        result, self.status_msg, self.execute_completed = result
        return result


class AsyncpgBufferedCursor(AsyncpgCursor):
    def __init__(self, dbapi, raw_conn):
        super().__init__(dbapi, raw_conn)
        self.result = []
        self.size = 0
        self.offset = 0

    async def _iterate(self, statement: str, parameters):
        self.result = await self._execute_and_fetch(statement, parameters)
        self.size = len(self.result)
        return True

    async def _fetchone(self):
        if self.offset < self.size:
            rv = self.result[self.offset]
            self.offset += 1
            return rv
        else:
            return None

    async def _fetchmany(self, size):
        rv = self.result[self.offset : self.offset + size]
        self.offset += size
        return rv

    async def _fetchall(self):
        rv = self.result[self.offset :]
        self.offset = self.size
        return rv

    async def _close(self, cursor):
        self.result.clear()


async def _cursor_fetchall(self, *, timeout=None):
    self._check_conn_validity("_cursor_fetchall")
    self._check_ready()
    if self._exhausted:
        return []
    recs = await self._exec(0, timeout)
    self._exhausted = True
    return recs


class AsyncpgSSCursor(AsyncpgCursor):
    raw_cursor: Optional[Cursor]

    def __init__(self, dbapi, raw_conn):
        super().__init__(dbapi, raw_conn)
        self.cursor_used = False

    async def _iterate(self, statement: str, parameters):
        stmt = await self.raw_conn.prepare(statement)
        self.set_attributes(stmt.get_attributes())
        return await stmt.cursor(*parameters)

    async def _fetchone(self):
        self.cursor_used = True
        return await self.raw_cursor.fetchrow()

    async def _fetchmany(self, size):
        self.cursor_used = True
        return await self.raw_cursor.fetch(size)

    async def _fetchall(self):
        self.cursor_used = True
        return await _cursor_fetchall(self.raw_cursor)

    async def _close(self, cursor):
        if not self.cursor_used:
            await cursor.fetchrow()


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


class PGExecutionContext_asyncpg(AsyncExecutionContext, PGExecutionContext):
    cursor_cls = AsyncpgBufferedCursor
    server_side_cursor_cls = AsyncpgSSCursor


class AsyncpgDialect(AsyncDialect, PGDialect):
    poolclass = AsyncPool
    execution_ctx_cls = PGExecutionContext_asyncpg
    statement_compiler = AsyncpgCompiler
    supports_server_side_cursors = True

    def __init__(self, server_side_cursors=False, **kwargs):
        super().__init__(**kwargs)
        self.server_side_cursors = server_side_cursors

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
