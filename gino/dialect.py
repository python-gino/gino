from sqlalchemy import cutils
from sqlalchemy.dialects.postgresql.base import (
    PGCompiler,
    PGDialect,
    PGExecutionContext,
)


class AsyncpgCompiler(PGCompiler):
    @property
    def bindtemplate(self):
        return self._bindtemplate

    @bindtemplate.setter
    def bindtemplate(self, val):
        # noinspection PyAttributeOutsideInit
        self._bindtemplate = val.replace(':', '$')


class NoopConnection:
    def __init__(self, dialect):
        self.dialect = dialect
        self._execution_options = {}

    def cursor(self):
        pass


# noinspection PyAbstractClass
class AsyncpgExecutionContext(PGExecutionContext):
    model = None

    @classmethod
    def init_clause(cls, dialect, elem, *multiparams, **params):
        # partially copied from:
        # sqlalchemy.engine.base.Connection:_execute_clauseelement
        # noinspection PyProtectedMember
        distilled_params = cutils._distill_params(multiparams, params)
        if distilled_params:
            # note this is usually dict but we support RowProxy
            # as well; but dict.keys() as an iterable is OK
            keys = distilled_params[0].keys()
        else:
            keys = []
        compiled_sql = elem.compile(
            dialect=dialect, column_keys=keys,
            inline=len(distilled_params) > 1,
        )
        conn = NoopConnection(dialect)
        rv = cls._init_compiled(
            dialect, conn, conn, compiled_sql, distilled_params)
        rv.guess_model(elem)
        return rv

    def guess_model(self, query):
        # query.__model__ is weak references, which need dereference
        model = getattr(query, '__model__', lambda: None)()
        if model is None:
            tables = getattr(query, 'froms', [])
            if len(tables) != 1:
                return
            model = getattr(tables[0], '__model__', lambda: None)()
            if not model:
                return
            for c in query.columns:
                if not hasattr(model, c.name):
                    return
        self.model = model

    def from_row(self, row):
        if self.model is None or row is None:
            return row
        rv = self.model()
        for key, value in row.items():
            type_ = getattr(getattr(self.model, key), 'type', None)
            if type_ is not None:
                processor = self.get_result_processor(type_, None, None)
                if processor:
                    value = processor(value)
            setattr(rv, key, value)
        return rv


class GinoCursorFactory:
    def __init__(self, env_factory, timeout, clause, *multiparams, **params):
        self._env_factory = env_factory
        self._context = None
        self._timeout = timeout
        self._clause = clause
        self._multiparams = multiparams
        self._params = params

    async def get_cursor_factory(self):
        connection, metadata = await self._env_factory()
        self._context = metadata.dialect.execution_ctx_cls.init_clause(
            metadata.dialect, self._clause, *self._multiparams, **self._params)
        return connection.cursor(self._context.statement,
                                 *self._context.parameters[0],
                                 timeout=self._timeout)

    @property
    def context(self):
        return self._context

    def __aiter__(self):
        return GinoCursorIterator(self)

    def __await__(self):
        return GinoCursor(self).async_init().__await__()


class GinoCursorIterator:
    def __init__(self, factory):
        self._factory = factory
        self._iterator = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._iterator is None:
            factory = await self._factory.get_cursor_factory()
            self._iterator = factory.__aiter__()
        row = await self._iterator.__anext__()
        return self._factory.context.from_row(row)


class GinoCursor:
    def __init__(self, factory):
        self._factory = factory
        self._cursor = None

    async def async_init(self):
        factory = await self._factory.get_cursor_factory()
        self._cursor = await factory
        return self

    async def many(self, n, *, timeout=None):
        rows = await self._cursor.fetch(n, timeout=timeout)
        return list(map(self._factory.context.from_row, rows))

    async def next(self, *, timeout=None):
        row = await self._cursor.fetchrow(timeout=timeout)
        return self._factory.context.from_row(row)

    def __getattr__(self, item):
        return getattr(self._cursor, item)


# noinspection PyAbstractClass
class AsyncpgDialect(PGDialect):
    default_paramstyle = 'numeric'
    statement_compiler = AsyncpgCompiler
    execution_ctx_cls = AsyncpgExecutionContext

    def compile(self, elem, *multiparams, **params):
        context = self.execution_ctx_cls.init_clause(
            self, elem, *multiparams, **params)
        return context.statement, context.parameters[0]

    def get_result_processor(self, col):
        # noinspection PyProtectedMember
        return col.type._cached_result_processor(self, None)

    async def do_all(self, bind, clause, *multiparams, timeout=None, **params):
        context = self.execution_ctx_cls.init_clause(
            self, clause, *multiparams, **params)
        rows = await bind.fetch(context.statement, *context.parameters[0],
                                timeout=timeout)
        return list(map(context.from_row, rows))

    async def do_first(self, bind, clause, *multiparams,
                       timeout=None, **params):
        context = self.execution_ctx_cls.init_clause(
            self, clause, *multiparams, **params)
        row = await bind.fetchrow(context.statement, *context.parameters[0],
                                  timeout=timeout)
        return context.from_row(row)

    async def do_scalar(self, bind, clause, *multiparams,
                        timeout=None, **params):
        context = self.execution_ctx_cls.init_clause(
            self, clause, *multiparams, **params)
        return await bind.fetchval(context.statement, *context.parameters[0],
                                   timeout=timeout)

    async def do_status(self, bind, clause, *multiparams,
                        timeout=None, **params):
        context = self.execution_ctx_cls.init_clause(
            self, clause, *multiparams, **params)
        return await bind.execute(context.statement, *context.parameters[0],
                                  timeout=timeout)
