from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from contextvars import ContextVar
from copy import copy
from typing import Union, Dict, Sequence, Optional, Any, TYPE_CHECKING

from sniffio import current_async_library
from sqlalchemy import cutils
from sqlalchemy.engine import create_engine as sa_create_engine
from sqlalchemy.engine import util
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.engine.url import make_url, URL
from sqlalchemy.exc import ObjectNotExecutableError, DBAPIError, InvalidRequestError
from sqlalchemy.future.engine import NO_OPTIONS
from sqlalchemy.sql import WARN_LINTING
from sqlalchemy.util import immutabledict, raise_

from .transaction import AsyncTransaction, TransactionContext

if TYPE_CHECKING:
    from typing_extensions import Protocol

    from .dialects.base import AsyncDialect
    from .pool.base import AsyncPool
    from .result import AsyncResult

    class Executable(Protocol):
        def _execute_on_connection(self, conn, multiparams, params, execution_options):
            ...


class AsyncConnection:
    __slots__ = (
        "_engine",
        "_execution_options",
        "_pool",
        "_dialect",
        "_raw_conn",
        "_reentrant_error",
        "_is_disconnect",
    )
    _execution_options: immutabledict
    _is_future = True
    _echo = False

    def __init__(self, engine: AsyncEngine, execution_options):
        self._engine = engine
        self._execution_options = execution_options
        self._pool = engine.pool
        self._dialect = engine.dialect
        self._raw_conn = None
        self._reentrant_error = False
        self._is_disconnect = False

    @property
    def dialect(self):
        return self._dialect

    @property
    def raw_connection(self):
        return self._raw_conn

    async def __async_init__(self) -> AsyncConnection:
        try:
            self._raw_conn = await self._pool.acquire()
        except BaseException as e:
            await self._handle_dbapi_exception(e, None, None, None, None)
        return self

    def __await__(self):
        return self.__async_init__().__await__()

    async def __aenter__(self):
        self._engine.current_connection
        return await self.__async_init__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _handle_dbapi_exception(self, e, statement, parameters, cursor, context):
        exc_info = sys.exc_info()

        is_exit_exception = not isinstance(e, Exception)

        if not self._is_disconnect:
            self._is_disconnect = (
                isinstance(e, self._dialect.dbapi.Error)
                and not self.closed
                and self._dialect.is_disconnect(e, self._raw_conn, cursor)
            ) or (is_exit_exception and not self.closed)

        if self._reentrant_error:
            raise_(
                DBAPIError.instance(
                    statement,
                    parameters,
                    e,
                    self._dialect.dbapi.Error,
                    hide_parameters=self._engine.hide_parameters,
                    dialect=self._dialect,
                    ismulti=context.executemany if context is not None else None,
                ),
                with_traceback=exc_info[2],
                from_=e,
            )
        self._reentrant_error = True
        try:
            # non-DBAPI error - if we already got a context,
            # or there's no string statement, don't wrap it
            should_wrap = isinstance(e, self._dialect.dbapi.Error) or (
                statement is not None and context is None and not is_exit_exception
            )

            if should_wrap:
                sqlalchemy_exception = DBAPIError.instance(
                    statement,
                    parameters,
                    e,
                    self._dialect.dbapi.Error,
                    hide_parameters=self._engine.hide_parameters,
                    connection_invalidated=self._is_disconnect,
                    dialect=self._dialect,
                    ismulti=context.executemany if context is not None else None,
                )
            else:
                sqlalchemy_exception = None

            if should_wrap and context:
                coro = context.handle_dbapi_exception(e)
                if hasattr(coro, "__await__"):
                    await coro

            if should_wrap:
                raise_(sqlalchemy_exception, with_traceback=exc_info[2], from_=e)
            else:
                raise_(exc_info[1], with_traceback=exc_info[2])

        finally:
            if self._is_disconnect:
                await self.close()

    def _execute_clauseelement(
        self, elem, multiparams=None, params=None, execution_options=NO_OPTIONS
    ):
        # noinspection PyProtectedMember
        distilled_params = cutils._distill_params(multiparams, params)
        if distilled_params:
            # ensure we don't retain a link to the view object for keys()
            # which links to the values, which we don't want to cache
            keys = list(distilled_params[0].keys())
        else:
            keys = []

        dialect = self._dialect
        compiled_sql = elem.compile(
            dialect=dialect,
            column_keys=keys,
            inline=len(distilled_params) > 1,
            schema_translate_map=None,
            linting=dialect.compiler_linting | WARN_LINTING,
        )
        # noinspection PyProtectedMember
        return dialect.execution_ctx_cls._init_compiled(
            dialect,
            self,
            self._raw_conn,
            execution_options,
            compiled_sql,
            distilled_params,
            elem,
            None,
        ).setup_result_proxy()

    def execution_options(self, **kwargs):
        self._execution_options = self._execution_options.union(kwargs)
        return self

    def execute(
        self,
        statement: Executable,
        parameters: Optional[Union[Dict[str, Any], Sequence[Any]]] = None,
        execution_options: Optional[Dict[str, Any]] = NO_OPTIONS,
    ) -> AsyncResult:
        if self._raw_conn is None:
            raise InvalidRequestError("This Connection is closed")
        # noinspection PyProtectedMember
        multiparams, params = util._distill_params_20(parameters)[:2]
        try:
            # noinspection PyProtectedMember
            meth = statement._execute_on_connection
        except AttributeError:
            raise ObjectNotExecutableError(statement)
        else:
            return meth(self, multiparams, params, execution_options)

    async def scalar(
        self,
        statement: Executable,
        parameters: Optional[Union[Dict[str, Any], Sequence[Any]]] = None,
        execution_options: Optional[Dict[str, Any]] = NO_OPTIONS,
    ) -> Any:
        return await self.execute(statement, parameters, execution_options).scalar()

    def begin(self) -> AsyncTransaction:
        return AsyncTransaction(self)

    transaction = begin

    async def close(self):
        conn, self._raw_conn = self._raw_conn, None
        if conn is not None:
            await self._pool.release(conn)

    @property
    def closed(self):
        return self._raw_conn is None


class AsyncEngine:
    connection_cls = AsyncConnection
    _execution_options = immutabledict()

    def __init__(
        self, pool, dialect, url, echo=False, hide_parameters=False,
    ):
        self._pool = pool
        self._dialect = dialect
        self._url = url
        self._echo = echo
        self._stack = ContextVar("current_connections_stack")
        self.hide_parameters = hide_parameters

    @property
    def pool(self) -> AsyncPool:
        return self._pool

    @property
    def dialect(self) -> Union[AsyncDialect, Dialect]:
        return self._dialect

    @property
    def url(self) -> URL:
        return self._url

    async def __async_init__(self):
        async with self.connect():
            return self

    def __await__(self):
        return self.__async_init__().__await__()

    async def __aenter__(self):
        return await self.__async_init__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        await self._pool.close()

    def connect(self) -> AsyncConnection:
        return self.connection_cls(self, self._execution_options)

    def begin(self) -> TransactionContext:
        return TransactionContext(self)

    transaction = begin

    class _EngineResult:
        __slots__ = "_engine", "_args", "_conn", "_result", "_ctx"
        _conn: Optional[AsyncConnection]
        _result: Optional[AsyncResult]

        def __init__(self, engine: AsyncEngine, *args):
            self._engine = engine
            self._args = args
            self._conn = None
            self._result = None
            self._ctx = None

        async def __aenter__(self):
            if self._ctx is not None:
                raise InvalidRequestError("")
            self._ctx = self._contextual_execute()
            return await self._ctx.__aenter__()

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            ctx, self._ctx = self._ctx, None
            if ctx is None:
                raise InvalidRequestError("")
            await ctx.__aexit__(exc_type, exc_val, exc_tb)

        def __await__(self):
            return self._execute().__await__()

        @asynccontextmanager
        async def _contextual_execute(self):
            async with self._engine.begin() as conn:
                async with conn.execute(*self._args) as result:
                    self._conn = conn
                    self._result = result
                    try:
                        yield
                    finally:
                        self._conn = None
                        self._result = None

        async def _execute(self):
            async with self._engine.begin() as conn:
                return await conn.execute(*self._args)

        async def _call_on_result(self, method, *args, **kwargs):
            if self._result is None:
                async with self._engine.begin() as conn:
                    return await getattr(conn.execute(*self._args), method)(
                        *args, **kwargs
                    )
            else:
                return getattr(self._result, method)(*args, **kwargs)

        async def fetchall(self):
            return await self._call_on_result("fetchall")

        async def fetchone(self):
            return await self._call_on_result("fetchone")

        async def fetchmany(self, size=None):
            return await self._call_on_result("fetchmany", size)

        async def all(self):
            return await self._call_on_result("all")

        async def first(self):
            return await self._call_on_result("first")

        async def one_or_none(self):
            return await self._call_on_result("one_or_none")

        async def one(self):
            return await self._call_on_result("one")

        async def scalar(self):
            return await self._call_on_result("scalar")

    def execute(
        self,
        statement: Executable,
        parameters: Optional[Union[Dict[str, Any], Sequence[Any]]] = None,
        execution_options: Optional[Dict[str, Any]] = NO_OPTIONS,
    ) -> _EngineResult:
        return self._EngineResult(self, statement, parameters, execution_options)

    async def scalar(
        self,
        statement: Executable,
        parameters: Optional[Union[Dict[str, Any], Sequence[Any]]] = None,
        execution_options: Optional[Dict[str, Any]] = NO_OPTIONS,
    ) -> Any:
        return await self.execute(statement, parameters, execution_options).scalar()


def create_engine(url: Union[str, URL], **kwargs) -> AsyncEngine:
    url = make_url(url)

    if url.drivername in {"postgresql", "postgres"}:
        url = copy(url)
        if current_async_library() == "asyncio":
            url.drivername = "postgresql+asyncpg"
        elif current_async_library() == "trio":
            url.drivername = "postgresql+triopg"

    if url.drivername in {"mysql"}:
        url = copy(url)
        if current_async_library() == "asyncio":
            url.drivername = "mysql+aiomysql"
        elif current_async_library() == "trio":
            url.drivername = "mysql+trio_mysql"

    kwargs["_future_engine_class"] = AsyncEngine

    return sa_create_engine(url, **kwargs)
