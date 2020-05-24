from __future__ import annotations

from collections import deque
from typing import Optional

from sqlalchemy.engine.cursor import (
    BufferedRowCursorFetchStrategy,
    CursorFetchStrategy,
    NoCursorDMLFetchStrategy,
)
from sqlalchemy.exc import InvalidRequestError


class AsyncCursorStrategy(CursorFetchStrategy):
    dbapi_cursor: AsyncCursor

    def yield_per(self, result, num):
        result._cursor_strategy = AsyncSSCursorStrategy(
            self.dbapi_cursor, self.cursor_description, num, deque(), growth_factor=0,
        )

    async def fetchone(self, result):
        try:
            return await self.dbapi_cursor.fetchone()
        except BaseException as e:
            await self.handle_exception(result, e)

    async def fetchmany(self, result, size=None):
        try:
            return await self.dbapi_cursor.fetchmany(size)
        except BaseException as e:
            await self.handle_exception(result, e)

    async def fetchall(self, result):
        try:
            return await self.dbapi_cursor.fetchall()
        except BaseException as e:
            await self.handle_exception(result, e)

    async def handle_exception(self, result, err):
        await result.connection._handle_dbapi_exception(
            err, None, None, self.dbapi_cursor, result.context
        )


class AsyncNoDMLStrategy(NoCursorDMLFetchStrategy):
    async def _non_result(self, result, default, err=None):
        super()._non_result(result, default, err)


_NO_CURSOR_DML = AsyncNoDMLStrategy()


class AsyncSSCursorStrategy(AsyncCursorStrategy, BufferedRowCursorFetchStrategy):
    @classmethod
    def create(cls, result):

        dbapi_cursor = result.cursor
        initial_buffer = deque()
        description = dbapi_cursor.description
        if description is None:
            return _NO_CURSOR_DML
        else:
            max_row_buffer = result.context.execution_options.get(
                "max_row_buffer", 1000
            )
            return cls(dbapi_cursor, description, max_row_buffer, initial_buffer)

    async def _buffer_rows(self, result):
        size = self._bufsize
        try:
            if size < 1:
                new_rows = await self.dbapi_cursor.fetchall()
            else:
                new_rows = await self.dbapi_cursor.fetchmany(size)
        except BaseException as e:
            await self.handle_exception(result, e)

        if not new_rows:
            return
        self._rowbuffer = deque(new_rows)
        if self._growth_factor and size < self._max_row_buffer:
            self._bufsize = min(self._max_row_buffer, size * self._growth_factor)

    async def fetchone(self, result):
        if not self._rowbuffer:
            await self._buffer_rows(result)
            if not self._rowbuffer:
                return None
        return self._rowbuffer.popleft()

    async def fetchmany(self, result, size=None):
        if size is None:
            return await self.fetchall(result)

        buf = list(self._rowbuffer)
        lb = len(buf)
        if size > lb:
            try:
                buf.extend(await self.dbapi_cursor.fetchmany(size - lb))
            except BaseException as e:
                await self.handle_exception(result, e)

        result = buf[0:size]
        self._rowbuffer = deque(buf[size:])
        return result

    async def fetchall(self, result):
        try:
            ret = list(self._rowbuffer) + list(await self.dbapi_cursor.fetchall())
            self._rowbuffer.clear()
            return ret
        except BaseException as e:
            await self.handle_exception(result, e)


class AsyncCursor:
    def __init__(self, dbapi, raw_conn):
        self.raw_conn = raw_conn
        self.raw_cursor = None
        self.description = None

    def _check_cursor_on_fetch(self):
        if self.raw_cursor is None:
            raise InvalidRequestError(
                "Cursor is closed. To use `fetch*()` multiple times, wrap it with "
                "`async with conn.execute(...):` block."
            )

    async def _execute_many(self, statement, parameters):
        raise NotImplementedError

    async def _execute_and_fetch(
        self, statement, parameters, *, limit: Optional[int] = None
    ):
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

    async def execute(self, context, *, fetch: Optional[int] = None):
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
                rv = await self._execute_and_fetch(context.statement, parameters)
            else:
                rv = await self._execute_and_fetch(
                    context.statement, parameters, limit=fetch
                )

        if context.compiled:
            coro = context.post_exec()
            if hasattr(coro, "__await__"):
                await coro

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
