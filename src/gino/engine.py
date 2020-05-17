from __future__ import annotations

import typing
from copy import copy
from typing import Union, Dict, Sequence, Optional, Any

from sqlalchemy import cutils
from sqlalchemy.engine import create_engine as sa_create_engine
from sqlalchemy.engine import util
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.engine.url import make_url, URL
from sqlalchemy.exc import ObjectNotExecutableError
from sqlalchemy.future.engine import NO_OPTIONS
from sqlalchemy.sql import WARN_LINTING, ClauseElement
from sqlalchemy.sql.compiler import Compiled
from sqlalchemy.sql.ddl import DDLElement
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.sql.schema import DefaultGenerator
from sqlalchemy.util import immutabledict

from .transaction import AsyncTransaction, TransactionContext

if typing.TYPE_CHECKING:
    from .dialects.base import AsyncDialect
    from .pool import AsyncPool
    from .result import AsyncResult

    try:

        class Executable(typing.Protocol):
            def _execute_on_connection(
                self, conn, multiparams, params, execution_options
            ):
                ...

    except AttributeError:
        Executable = Union[
            ClauseElement, FunctionElement, DDLElement, DefaultGenerator, Compiled
        ]


class AsyncConnection:
    __slots__ = ("_execution_options", "_pool", "_dialect", "_raw_conn")
    _execution_options: immutabledict
    _is_future = True
    _echo = False

    def __init__(self, engine: AsyncEngine, execution_options):
        self._execution_options = execution_options
        self._pool = engine.pool
        self._dialect = engine.dialect
        self._raw_conn = None

    @property
    def dialect(self):
        return self._dialect

    @property
    def raw_connection(self):
        return self._raw_conn

    async def __async_init__(self) -> AsyncConnection:
        self._raw_conn = await self._pool.acquire()
        return self

    def __await__(self):
        return self.__async_init__().__await__()

    async def __aenter__(self):
        return await self.__async_init__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
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
        # noinspection PyProtectedMember
        multiparams, params, distilled_parameters = util._distill_params_20(parameters)
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

    async def close(self):
        conn, self._raw_conn = self._raw_conn, None
        await self._pool.release(conn)


class AsyncEngine:
    connection_cls = AsyncConnection
    _execution_options = immutabledict()

    def __init__(self, pool, dialect, url, echo=False):
        self._pool = pool
        self._dialect = dialect
        self._url = url
        self._echo = echo

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
        return self

    def __await__(self):
        return self.__async_init__().__await__()

    def connect(self) -> connection_cls:
        return self.connection_cls(self, self._execution_options)

    def begin(self) -> TransactionContext:
        return TransactionContext(self)

    transaction = begin


async def create_engine(url: Union[str, URL], **kwargs) -> AsyncEngine:
    url = make_url(url)

    if url.drivername in {"postgresql", "postgres"}:
        url = copy(url)
        url.drivername = "postgresql+asyncpg"

    if url.drivername in {"mysql"}:
        url = copy(url)
        url.drivername = "mysql+aiomysql"

    kwargs["_future_engine_class"] = AsyncEngine

    return await sa_create_engine(url, **kwargs)
