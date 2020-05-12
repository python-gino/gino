from sqlalchemy.cutils import _distill_params
from sqlalchemy.engine.util import _distill_params_20
from sqlalchemy.exc import ObjectNotExecutableError
from sqlalchemy.future.engine import NO_OPTIONS
from sqlalchemy.sql import WARN_LINTING
from sqlalchemy.util import safe_reraise, immutabledict

from .errors import InterfaceError


class AsyncTransaction:
    def __init__(self, conn):
        self._conn = conn
        self._tx = None
        self._managed = None

    async def _begin(self):
        self._tx = await self._conn._begin_impl()
        return self

    async def _commit(self):
        await self._conn._commit_impl(self._tx)

    async def _rollback(self):
        await self._conn._rollback_impl(self._tx)

    async def __async_init__(self):
        if self._managed is not None:
            raise InterfaceError("Transaction already started")
        self._managed = False
        return await self._begin()

    async def commit(self):
        if self._managed is None:
            raise InterfaceError("Transaction not started")
        if self._managed:
            raise InterfaceError("Transaction is managed")
        await self._commit()

    async def rollback(self):
        if self._managed is None:
            raise InterfaceError("Transaction not started")
        if self._managed:
            raise InterfaceError("Transaction is managed")
        await self._rollback()

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


class AsyncConnection:
    _is_future = True
    _execution_options = None
    _echo = False

    def __init__(self, engine):
        self._engine = engine
        self._raw_conn = None

    async def __async_init__(self):
        self._raw_conn = await self._engine.raw_connection()
        return self

    def __await__(self):
        return self.__async_init__().__await__()

    @property
    def dialect(self):
        return self._engine.dialect

    def begin(self):
        return AsyncTransaction(self)

    async def close(self):
        conn, self._raw_conn = self._raw_conn, None
        await self._engine.release_raw_connection(conn)

    class _ExecuteContext:
        def __init__(self, conn, statement, parameters, execution_options):
            self._conn = conn
            self._statement = statement
            self._parameters = parameters
            self._execution_options = immutabledict(execution_options or {})
            self._result = None

        async def __async_init__(self, *, stream_results=None):
            multiparams, params, distilled_parameters = _distill_params_20(
                self._parameters
            )
            try:
                meth = self._statement._execute_on_connection
            except AttributeError:
                raise ObjectNotExecutableError(self._statement)
            else:
                opts = self._execution_options
                if stream_results is not None:
                    opts = opts.union({"stream_results": stream_results})
                self._result = await meth(self._conn, multiparams, params, opts)
                return self._result

        def __await__(self):
            return self.__async_init__().__await__()

        async def __aenter__(self):
            return await self.__async_init__(stream_results=True)

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            await self._result.close()

    def execute(self, statement, parameters=None, execution_options=None):
        return self._ExecuteContext(self, statement, parameters, execution_options)

    async def _begin_impl(self):
        return await self._engine.dialect.do_begin(self._raw_conn)

    async def _commit_impl(self, tx):
        await self._engine.dialect.do_commit(tx)

    async def _rollback_impl(self, tx):
        await self._engine.dialect.do_rollback(tx)

    async def _execute_clauseelement(
        self, elem, multiparams=None, params=None, execution_options=NO_OPTIONS
    ):
        distilled_params = _distill_params(multiparams, params)
        if distilled_params:
            # ensure we don't retain a link to the view object for keys()
            # which links to the values, which we don't want to cache
            keys = list(distilled_params[0].keys())
        else:
            keys = []

        dialect = self._engine.dialect
        extracted_params = None
        compiled_sql = elem.compile(
            dialect=dialect,
            column_keys=keys,
            inline=len(distilled_params) > 1,
            schema_translate_map=None,
            linting=dialect.compiler_linting | WARN_LINTING,
        )
        return await self._execute_context(
            dialect,
            dialect.execution_ctx_cls._init_compiled,
            compiled_sql,
            distilled_params,
            execution_options,
            compiled_sql,
            distilled_params,
            elem,
            extracted_params,
        )

    async def _execute_context(
        self, dialect, constructor, statement, parameters, execution_options, *args
    ):
        context = constructor(dialect, self, self._raw_conn, execution_options, *args)
        if context.compiled:
            coro = context.pre_exec()
            if hasattr(coro, "__await__"):
                await coro

        cursor, statement, parameters = (
            context.cursor,
            context.statement,
            context.parameters,
        )

        if not context.executemany:
            parameters = parameters[0]

        if context.executemany:
            dialect.do_executemany(cursor, statement, parameters, context)
        elif not parameters and context.no_parameters:
            dialect.do_execute_no_params(cursor, statement, context)
        else:
            await dialect.do_execute(cursor, statement, parameters, context)

        if context.compiled:
            coro = context.post_exec()
            if hasattr(coro, "__await__"):
                await coro

        return context._setup_result_proxy()


class AsyncEngine:
    _connection_cls = AsyncConnection

    def __init__(self, pool, dialect, url, echo=False):
        self._pool = pool
        self._dialect = dialect
        self._url = url
        self._echo = echo

    @property
    def dialect(self):
        return self._dialect

    class _ConnectCtx:
        def __init__(self, engine):
            self.engine = engine
            self.conn = None

        def connect(self):
            self.conn = self.engine._connection_cls(self.engine)
            return self.conn

        def __await__(self):
            return self.connect().__await__()

        async def __aenter__(self):
            return await self.connect()

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            await self.conn.close()

    def connect(self):
        return self._ConnectCtx(self)

    class _TransCtx:
        def __init__(self, engine):
            self.engine = engine
            self.conn = None
            self.transaction = None

        async def __aenter__(self):
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

    def begin(self):
        return self._TransCtx(self)

    async def raw_connection(self):
        return await self._pool.acquire()

    async def release_raw_connection(self, conn):
        return await self._pool.release(conn)
