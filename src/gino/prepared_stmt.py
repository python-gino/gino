from __future__ import annotations

import abc

from sqlalchemy.ext.asyncio.base import StartableContext
from .engine import GinoConnection


class PreparedStatement(StartableContext, abc.ABC):
    __slots__ = ("_clause", "_conn", "_prepared")
    _conn: GinoConnection

    def __init__(self, conn, clause):
        self._conn = conn
        self._clause = clause
        self._prepared = None

    async def start(self, is_ctxmanager=False) -> PreparedStatement:
        self._prepared = await self._conn.execute(
            self._clause,
            _do_load=False,
            execution_options=dict(
                compile_only=True, check_args=False, do_prepare=True
            ),
        )
        return self

    async def __aexit__(self, type_, value, traceback):
        if self._prepared is None:
            self._raise_for_not_started()

    def _get_prepared(self):
        if self._prepared is None:
            self._raise_for_not_started()
        return self._prepared

    def iterate(self, *params, **kwargs):
        return _PreparedIterableCursor(self, params, kwargs)

    async def all(self, *multiparams, **params):
        return await self._conn.all(
            self._clause,
            *multiparams,
            execution_options=dict(prepared_stmt=self),
            **params
        )

    async def first(self, *multiparams, **params):
        return await self._conn.first(
            self._clause,
            *multiparams,
            execution_options=dict(prepared_stmt=self),
            **params
        )

    async def scalar(self, *multiparams, **params):
        return await self._conn.scalar(
            self._clause,
            *multiparams,
            execution_options=dict(prepared_stmt=self),
            **params
        )

    async def status(self, *multiparams, **params):
        return await self._conn.status(
            self._clause,
            *multiparams,
            execution_options=dict(prepared_stmt=self),
            **params
        )
