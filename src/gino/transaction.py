from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.util import safe_reraise

if TYPE_CHECKING:
    from .engine import AsyncConnection


class _Break(BaseException):
    def __init__(self, tx, commit):
        super().__init__()
        self.tx = tx
        self.commit = commit


class AsyncTransaction:
    __slots__ = "_dialect", "_raw_conn", "_tx", "_managed"
    _managed: Optional[bool]

    def __init__(self, conn: AsyncConnection):
        self._dialect = conn.dialect
        self._raw_conn = conn.raw_connection
        self._tx = None
        self._managed = None

    async def __async_init__(self) -> AsyncTransaction:
        self._ensure_started(False)
        self._managed = False
        await self._begin()
        return self

    def __await__(self):
        return self.__async_init__().__await__()

    async def __aenter__(self):
        self._ensure_started(False)
        self._managed = True
        return await self._begin()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._ensure_managed()
        is_break = exc_type is _Break
        if exc_val.commit if is_break else exc_type is None:
            # noinspection PyBroadException
            try:
                await self._commit()
            except BaseException:
                with safe_reraise():
                    await self._rollback()
        else:
            await self._rollback()
        if is_break and exc_val.tx is self:
            return True

    def _ensure_started(self, expect=True):
        started = self._managed is not None
        if started != expect:
            if started:
                raise InvalidRequestError("Transaction already started")
            else:
                raise InvalidRequestError("Transaction is not started")

    def _ensure_managed(self, managed=True):
        self._ensure_started()

        if self._managed != managed:
            if self._managed:
                raise InvalidRequestError("Transaction is managed")
            else:
                raise InvalidRequestError("Transaction is not managed")

    async def _begin(self):
        self._tx = await self._dialect.do_begin(self._raw_conn)
        return self

    async def _commit(self):
        await self._dialect.do_commit(self._tx)

    async def _rollback(self):
        await self._dialect.do_rollback(self._tx)

    async def commit(self) -> None:
        self._ensure_managed(False)
        await self._commit()

    async def rollback(self) -> None:
        self._ensure_managed(False)
        await self._rollback()

    def raise_commit(self):
        self._ensure_managed()
        raise _Break(self, True)

    def raise_rollback(self):
        self._ensure_managed()
        raise _Break(self, False)


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
        except Exception:
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
