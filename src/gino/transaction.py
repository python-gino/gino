from __future__ import annotations

import typing

from sqlalchemy.util import safe_reraise

from .errors import InterfaceError

if typing.TYPE_CHECKING:
    from .engine import AsyncConnection


class AsyncTransaction:
    def __init__(self, conn: AsyncConnection):
        self._dialect = conn.dialect
        self._raw_conn = conn.raw_connection
        self._tx = None
        self._managed = None

    async def __async_init__(self) -> AsyncTransaction:
        if self._managed is not None:
            raise InterfaceError("Transaction already started")
        self._managed = False
        await self._begin()
        return self

    def __await__(self):
        return self.__async_init__().__await__()

    async def __aenter__(self):
        if self._managed is not None:
            raise InterfaceError("Transaction already started")
        self._managed = True
        return await self._begin()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self._commit()
        else:
            await self._rollback()

    async def _begin(self):
        self._tx = await self._dialect.do_begin(self._raw_conn)
        return self

    async def _commit(self):
        await self._dialect.do_commit(self._tx)

    async def _rollback(self):
        await self._dialect.do_rollback(self._tx)

    async def commit(self) -> None:
        if self._managed is None:
            raise InterfaceError("Transaction not started")
        if self._managed:
            raise InterfaceError("Transaction is managed")
        await self._commit()

    async def rollback(self) -> None:
        if self._managed is None:
            raise InterfaceError("Transaction not started")
        if self._managed:
            raise InterfaceError("Transaction is managed")
        await self._rollback()


class TransactionContext:
    def __init__(self, engine):
        self.engine = engine
        self.conn = None
        self.transaction = None

    async def __aenter__(self) -> AsyncConnection:
        conn = await self.engine.connect()
        # noinspection PyBroadException
        try:
            self.transaction, self.conn = await conn.begin(), conn
        except:  # noqa
            with safe_reraise():
                await conn.close()
        return conn

    async def __aexit__(self, type_, value, traceback):
        try:
            if type_ is None:
                await self.transaction.commit()
            else:
                await self.transaction.rollback()
        finally:
            await self.conn.close()
