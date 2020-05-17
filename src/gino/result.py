from __future__ import annotations

import typing

from sqlalchemy.engine.cursor import CursorResultMetaData, _no_result_metadata
from sqlalchemy.engine.result import Result, _NO_ROW
from sqlalchemy.exc import InvalidRequestError, NoResultFound, MultipleResultsFound
from sqlalchemy.util import HasMemoized

from .errors import InterfaceError

if typing.TYPE_CHECKING:
    from .dialects.base import AsyncExecutionContext, AsyncCursor


class AsyncResult(Result):
    _cursor: AsyncCursor
    _cursor_metadata = CursorResultMetaData

    # noinspection PyMissingConstructor
    def __init__(self, context: AsyncExecutionContext):
        self._context = context
        self._dialect = context.dialect
        self._cursor = context.cursor
        self._ctx_count = 0
        self._prepared = False
        self._initialized = False

    @property
    def context(self):
        return self._context

    async def __aenter__(self):
        self._ctx_count += 1
        if not self._prepared:
            self._prepared = True
            await self._cursor.execute(self._context, fetch=0)
        if not self._initialized:
            self._initialized = True
            if self._cursor.description is not None:
                if self._context.compiled:
                    if self._context.compiled._cached_metadata:
                        cached_md = self._context.compiled._cached_metadata
                        metadata = cached_md._adapt_to_context(self._context)

                    else:
                        metadata = (
                            self._context.compiled._cached_metadata
                        ) = self._cursor_metadata(self, self._cursor.description)
                else:
                    metadata = self._cursor_metadata(self, self._cursor.description)
            else:
                metadata = _no_result_metadata
            super().__init__(metadata)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._ctx_count -= 1
        if self._ctx_count == 0:
            await self._cursor.close()

    def __await__(self):
        return self._execute().__await__()

    def __iter__(self):
        raise NotImplementedError("Please use `async for` instead.")

    def __next__(self):
        raise NotImplementedError("Please use `async for` instead.")

    next = __next__

    def __aiter__(self):
        return self._iterator_getter()

    def __ensure_init__(self):
        self._prepared = True
        return self

    async def _execute(self) -> None:
        if self._prepared:
            raise InterfaceError("Cannot await on an AsyncResult more than once.")
        async with self.__ensure_init__():
            await self._cursor.execute(self._context)

    async def _iterator_getter(self):
        async with self:
            while True:
                row = await self._onerow_getter()
                if row is _NO_ROW:
                    break
                yield row

    @HasMemoized.memoized_attribute
    def _allrow_getter(self):
        async def allrows(self):
            if self._prepared:
                rows = await self._cursor.fetchall()
            else:
                rows = await self._cursor.execute(self._context, fetch=-1)
            async with self.__ensure_init__():
                make_row = self._row_getter()
                post_creational_filter = self._post_creational_filter

                if self._unique_filter_state:
                    uniques, strategy = self._unique_strategy
                    rows = [
                        made_row
                        for made_row, sig_row in [
                            (made_row, strategy(made_row) if strategy else made_row,)
                            for made_row in [make_row(row) for row in rows]
                        ]
                        if sig_row not in uniques and not uniques.add(sig_row)
                    ]

                    if post_creational_filter:
                        rows = [post_creational_filter(row) for row in rows]
                else:
                    if post_creational_filter:
                        rows = [post_creational_filter(make_row(row)) for row in rows]
                    else:
                        rows = [make_row(row) for row in rows]
                return rows

        return allrows

    async def _onerow_getter(self):
        # TODO: this is a lot for results that are only one row.
        # all of this could be in _only_one_row except for fetchone()
        # and maybe __next__
        post_creational_filter = self._post_creational_filter

        if self._unique_filter_state:
            async with self:
                make_row = self._row_getter()
                uniques, strategy = self._unique_strategy

                while True:
                    row = await self._cursor.fetchone()
                    if row is None:
                        return _NO_ROW
                    obj = make_row(row)
                    hashed = strategy(obj) if strategy else obj
                    if hashed in uniques:
                        continue
                    else:
                        uniques.add(hashed)
                    if post_creational_filter:
                        obj = post_creational_filter(obj)
                    return obj
        else:
            if self._prepared:
                row = await self._cursor.fetchone()
            else:
                rows = await self._cursor.execute(self._context, fetch=1)
                row = rows[0] if rows else None
            async with self.__ensure_init__():
                if row is None:
                    return _NO_ROW
                row = self._row_getter()(row)
                if post_creational_filter:
                    row = post_creational_filter(row)
                return row

    @HasMemoized.memoized_attribute
    def _manyrow_getter(self):
        post_creational_filter = self._post_creational_filter

        if self._unique_filter_state:

            def filterrows(make_row, rows, strategy, uniques):
                return [
                    made_row
                    for made_row, sig_row in [
                        (made_row, strategy(made_row) if strategy else made_row,)
                        for made_row in [make_row(row) for row in rows]
                    ]
                    if sig_row not in uniques and not uniques.add(sig_row)
                ]

            async def manyrows(self: AsyncResult, num):
                if num is None:
                    num = self._yield_per
                if num is None:
                    return await self._allrow_getter(self)

                async with self:
                    uniques, strategy = self._unique_strategy
                    collect = []
                    make_row = self._row_getter()
                    num_required = num
                    while num_required:
                        rows = await self._cursor.fetchmany(num_required)
                        if not rows:
                            break

                        collect.extend(filterrows(make_row, rows, strategy, uniques))
                        num_required = num - len(collect)

                    if post_creational_filter:
                        collect = [post_creational_filter(row) for row in collect]
                    return collect

        else:

            async def manyrows(self: AsyncResult, num):
                if num is None:
                    num = self._yield_per
                if num is None:
                    return await self._allrow_getter(self)

                if self._prepared:
                    rows = await self._cursor.fetchmany(num)
                else:
                    rows = await self._cursor.execute(self._context, fetch=num)
                async with self.__ensure_init__():
                    make_row = self._row_getter()
                    rows = [make_row(row) for row in rows]
                    if post_creational_filter:
                        rows = [post_creational_filter(row) for row in rows]
                    return rows

        return manyrows

    async def _only_one_row(self, raise_for_second_row, raise_for_none):
        if self._prepared:
            raise InterfaceError(
                "first/one*/scalar() cannot be used in `async with conn.execute(...)` "
                "block, use them directly like `await conn.execute(...).first()`, "
                "or use fetchone() instead."
            )

        async def do():
            row = await self._onerow_getter()
            if row is _NO_ROW:
                if raise_for_none:
                    raise NoResultFound("No row was found when one was required")
                else:
                    return None
            else:
                if raise_for_second_row:
                    next_row = await self._onerow_getter()
                else:
                    next_row = _NO_ROW
                if next_row is not _NO_ROW:
                    raise MultipleResultsFound(
                        "Multiple rows were found when exactly one was required"
                        if raise_for_none
                        else "Multiple rows were found when one or none " "was required"
                    )
                else:
                    return row

        if raise_for_second_row:
            async with self:
                return await do()
        else:
            return await do()

    async def fetchone(self):
        if self._no_scalar_onerow:
            raise InvalidRequestError(
                "Can't use fetchone() when returning scalar values; there's "
                "no way to distinguish between end of results and None"
            )

        row = await self._onerow_getter()
        if row is _NO_ROW:
            return None
        else:
            return row

    async def scalar(self):
        row = await self.first()
        if row is not None:
            return row[0]
        else:
            return None
