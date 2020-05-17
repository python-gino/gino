from __future__ import annotations

from typing import Optional, Union, Sequence, Dict, TYPE_CHECKING, Any

from sqlalchemy.engine.default import DefaultExecutionContext
from sqlalchemy.util import immutabledict

from ..errors import InterfaceError
from ..result import AsyncResult

if TYPE_CHECKING:
    from sqlalchemy.sql.compiler import Compiled

NO_OPTIONS = immutabledict()


class DBAPI:
    paramstyle = "numeric"
    connect = None


class AsyncCursor:
    def __init__(self, raw_conn):
        self.raw_conn = raw_conn
        self.raw_cursor = None
        self.description = None

    def _check_cursor_on_fetch(self):
        if self.raw_cursor is None:
            raise InterfaceError(
                "Cursor is closed. To use `fetch*()` multiple times, wrap it with "
                "`async with conn.execute(...):` block."
            )

    async def _execute_many(self, statement, parameters):
        raise NotImplementedError

    async def _execute(self, statement, parameters, *, limit: Optional[int] = None):
        raise NotImplementedError

    async def _iterate(self, statement: str, parameters):
        raise NotImplementedError()

    async def _fetchone(self):
        raise NotImplementedError()

    async def _fetchmany(self, size):
        raise NotImplementedError()

    async def _fetchall(self):
        raise NotImplementedError()

    async def _close(self, cursor):
        raise NotImplementedError()

    async def execute(
        self, context: AsyncExecutionContext, *, fetch: Optional[int] = None
    ):
        """

        :param context:
        :param fetch:
            * None: prepare only
            * -1: fetch all
            * 0: exhaust all
            * int: fetch exactly this number of results
        :return:
        """
        rv = None

        if context.compiled:
            coro = context.pre_exec()
            if hasattr(coro, "__await__"):
                await coro

        parameters = context.parameters
        if context.executemany:
            if fetch:
                raise ValueError("executemany returns no result")
            await self._execute_many(context.statement, parameters)
        else:
            parameters = parameters[0]
            if fetch == 0:
                self.raw_cursor = await self._iterate(context.statement, parameters)
            elif fetch == -1:
                rv = await self._execute(context.statement, parameters)
            else:
                rv = await self._execute(context.statement, parameters, limit=fetch)

        try:
            if context.compiled:
                coro = context.post_exec()
                if hasattr(coro, "__await__"):
                    await coro
        except Exception:
            await self.close()
            raise

        return rv

    async def fetchone(self):
        self._check_cursor_on_fetch()
        return await self._fetchone()

    async def fetchmany(self, num):
        self._check_cursor_on_fetch()
        if num is None:
            return await self._fetchall()
        return await self._fetchmany(num)

    async def fetchall(self):
        self._check_cursor_on_fetch()
        return await self._fetchall()

    async def close(self):
        cursor, self.raw_cursor = self.raw_cursor, None
        if cursor is not None:
            await self._close(cursor)


# noinspection PyAbstractClass
class AsyncExecutionContext(DefaultExecutionContext):
    if TYPE_CHECKING:
        dialect: AsyncDialect
        cursor: AsyncCursor
        compiled: Optional[Compiled]
        statement: str
        parameters: Union[Sequence, Dict]
        executemany: bool
        no_parameters: bool
        _dbapi_connection: Any

    cursor_cls = NotImplemented
    server_side_cursor_cls = None

    def create_cursor(self):
        if self._use_server_side_cursor() and self.server_side_cursor_cls:
            self._is_server_side = True
            cls = self.server_side_cursor_cls
        else:
            self._is_server_side = False
            cls = self.cursor_cls
        return cls(self._dbapi_connection)

    def setup_result_proxy(self) -> AsyncResult:
        return AsyncResult(self)


class AsyncDialect:
    execution_ctx_cls = AsyncExecutionContext
    compiler_linting: int
