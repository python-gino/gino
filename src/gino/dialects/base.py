from sqlalchemy.engine import Result
from sqlalchemy.engine.cursor import CursorResultMetaData, _no_result_metadata
from sqlalchemy.util import immutabledict, HasMemoized

NO_OPTIONS = immutabledict()


class AsyncResult(Result):
    _cursor_metadata = CursorResultMetaData

    def __init__(self, context):
        self.context = context
        self.dialect = context.dialect
        self.cursor = context.cursor
        self.connection = context.root_connection
        self._echo = self.connection._echo and context.engine._should_log_debug()
        super().__init__(self._init_metadata())

    def _init_metadata(self):
        self.cursor_strategy = strat = self.context.get_result_cursor_strategy(self)

        if strat.cursor_description is not None:
            if self.context.compiled:
                if self.context.compiled._cached_metadata:
                    cached_md = self.context.compiled._cached_metadata
                    metadata = cached_md._adapt_to_context(self.context)

                else:
                    metadata = (
                        self.context.compiled._cached_metadata
                    ) = self._cursor_metadata(self, strat.cursor_description)
            else:
                metadata = self._cursor_metadata(self, strat.cursor_description)
            if self._echo:
                self.context.engine.logger.debug(
                    "Col %r", tuple(x[0] for x in strat.cursor_description)
                )
        else:
            metadata = _no_result_metadata
        return metadata

    @HasMemoized.memoized_attribute
    def _allrow_getter(self):

        make_row = self._row_getter()

        post_creational_filter = self._post_creational_filter

        if self._unique_filter_state:
            uniques, strategy = self._unique_strategy

            async def allrows(self):
                rows = await self._fetchall_impl()
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
                return rows

        else:

            async def allrows(self):
                rows = await self._fetchall_impl()
                if post_creational_filter:
                    rows = [post_creational_filter(make_row(row)) for row in rows]
                else:
                    rows = [make_row(row) for row in rows]
                return rows

        return allrows

    async def _fetchall_impl(self):
        return await self.cursor.fetchall()

    async def close(self):
        pass


class AsyncCursor:
    def __init__(self, raw_conn):
        self.raw_conn = raw_conn

    @property
    def description(self):
        raise NotImplementedError

    async def execute(self, statement, parameters):
        raise NotImplementedError()

    async def fetchall(self):
        raise NotImplementedError()


class AsyncExecutionContextOverride:
    cursor_cls = None
    server_side_cursor_cls = None

    def create_cursor(self):
        if self._use_server_side_cursor() and self.server_side_cursor_cls:
            self._is_server_side = True
            cls = self.server_side_cursor_cls
        else:
            self._is_server_side = False
            cls = self.cursor_cls
        return cls(self._dbapi_connection)

    def _setup_result_proxy(self):
        result = AsyncResult(self)
        if self.compiled and not self.isddl and self.compiled.has_out_parameters:
            self._setup_out_parameters(result)
        return result


class DBAPI:
    paramstyle = "numeric"


class AsyncDialectOverride:
    async def do_execute(self, cursor, statement, parameters, context=None):
        await cursor.execute(statement, parameters)
