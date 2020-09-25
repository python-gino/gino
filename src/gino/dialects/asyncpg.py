import re

from sqlalchemy.dialects.postgresql.asyncpg import (
    AsyncAdapt_asyncpg_cursor,
    AsyncAdapt_asyncpg_ss_cursor,
    PGCompiler_asyncpg,
    PGDialect_asyncpg,
    PGExecutionContext_asyncpg,
)
from sqlalchemy.dialects.postgresql.base import PGDialect
from .base import (
    GinoCompilerOverride,
    GinoExecutionContextOverride,
    PreparedCursorOverride,
    PrepareOnlyCursorOverride,
)


class PrepareOnlyCursor(PrepareOnlyCursorOverride, AsyncAdapt_asyncpg_cursor):
    def _compile(self, operation):
        params = self._parameters()
        return re.sub(r"\?", lambda m: next(params), operation)

    def _prepare(self, operation):
        return self._adapt_connection.await_(self._connection.prepare(operation))


class CursorOverride(PreparedCursorOverride):
    async def _prepare_and_execute(self, operation, parameters):
        if not self._adapt_connection._started:
            await self._adapt_connection._start_transaction()

        params = self._parameters()
        operation = re.sub(r"\?", lambda m: next(params), operation)

        try:
            prepared = self._get_prepared_result()
            assert operation == prepared.operation
            prepared_stmt = prepared.payload

            attributes = prepared_stmt.get_attributes()
            if attributes:
                self.description = [
                    (attr.name, attr.type.oid, None, None, None, None, None)
                    for attr in attributes
                ]
            else:
                self.description = None

            if self.server_side:
                self._cursor = await prepared_stmt.cursor(*parameters)
                self.rowcount = -1
            else:
                self._rows = await prepared_stmt.fetch(*parameters)
                status = prepared_stmt.get_statusmsg()

                reg = re.match(r"(?:UPDATE|DELETE|SELECT|INSERT \d+) (\d+)", status)
                if reg:
                    self.rowcount = int(reg.group(1))
                else:
                    self.rowcount = -1

        except Exception as error:
            self._handle_exception(error)


class PreparedCursor(CursorOverride, AsyncAdapt_asyncpg_cursor):
    pass


class PreparedServerSideCursor(CursorOverride, AsyncAdapt_asyncpg_ss_cursor):
    pass


class AsyncpgExecutionContext(GinoExecutionContextOverride, PGExecutionContext_asyncpg):
    prepare_only_cursor = PrepareOnlyCursor
    prepared_cursor = PreparedCursor
    prepared_ss_cursor = PreparedServerSideCursor


class AsyncpgCompiler(GinoCompilerOverride, PGCompiler_asyncpg):
    pass


class AsyncpgDialect(PGDialect_asyncpg):
    execution_ctx_cls = AsyncpgExecutionContext
    statement_compiler = AsyncpgCompiler

    def on_connect(self):
        super_connect = super().on_connect()

        def connect(conn):
            if super_connect is not None:
                super_connect(conn)
            if self.isolation_level is not None:
                PGDialect.set_isolation_level(self, conn, self.isolation_level)

        return connect
