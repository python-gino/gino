from __future__ import annotations

from typing import Optional, Union, Sequence, Dict, TYPE_CHECKING, Any, Tuple, Type

from sniffio import current_async_library
from sqlalchemy.engine.default import DefaultExecutionContext
from sqlalchemy.util import immutabledict

from .cursor import AsyncCursor, AsyncCursorStrategy, AsyncSSCursorStrategy
from ..result import AsyncResult

if TYPE_CHECKING:
    from sqlalchemy.sql.compiler import Compiled

NO_OPTIONS = immutabledict()


class DBAPI:
    paramstyle = "numeric"
    connect: Any
    Error: Union[type, Tuple[type]]


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
        root_connection: Any
        _dbapi_connection: Any

    cursor_cls = NotImplemented
    server_side_cursor_cls: Optional[Type[AsyncCursor]] = None
    cursor_strategy_cls = AsyncCursorStrategy
    server_side_cursor_strategy_cls = AsyncSSCursorStrategy

    def create_cursor(self):
        if self._use_server_side_cursor() and self.server_side_cursor_cls:
            self._is_server_side = True
            cls = self.server_side_cursor_cls
        else:
            self._is_server_side = False
            cls = self.cursor_cls
        return cls(self.dialect.dbapi, self._dbapi_connection)

    def setup_result_proxy(self) -> AsyncResult:
        return AsyncResult(self)

    def get_result_cursor_strategy(self, result):
        if self._is_server_side:
            strat_cls = self.server_side_cursor_strategy_cls
        else:
            strat_cls = self.cursor_strategy_cls

        return strat_cls.create(result)


class AsyncDialect:
    execution_ctx_cls = AsyncExecutionContext
    compiler_linting: int
    dbapi: DBAPI

    @classmethod
    def get_pool_class(cls, url):
        if current_async_library() == "asyncio":
            from ..pool.aio import QueuePool

            return QueuePool
        elif current_async_library() == "trio":
            from ..pool.trio import QueuePool

            return QueuePool

    async def disconnect(self, conn):
        raise NotImplementedError()

    async def do_reset(self, conn, **kwargs):
        raise NotImplementedError()
