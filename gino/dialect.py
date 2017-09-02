import weakref

from sqlalchemy import cutils, util
from sqlalchemy.dialects.postgresql.base import (
    PGCompiler,
    PGDialect,
    PGExecutionContext,
)

from .record import update_record

DEFAULT = object()


class AsyncpgCompiler(PGCompiler):
    @property
    def bindtemplate(self):
        return self._bindtemplate

    @bindtemplate.setter
    def bindtemplate(self, val):
        # noinspection PyAttributeOutsideInit
        self._bindtemplate = val.replace(':', '$')


class NoopConnection:
    def __init__(self, dialect, execution_options):
        self.dialect = dialect
        self._execution_options = execution_options or {}

    def cursor(self):
        pass


# noinspection PyAbstractClass
class AsyncpgExecutionContext(PGExecutionContext):
    @classmethod
    def init_clause(cls, dialect, elem, multiparams, params,
                    execution_options):
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
        if execution_options:
            execution_options = dict(execution_options)
        else:
            execution_options = {}
        for opt in ('return_model', 'model', 'timeout'):
            if opt in compiled_sql.execution_options:
                execution_options.pop(opt, None)
        conn = NoopConnection(dialect, execution_options)
        rv = cls._init_compiled(
            dialect, conn, conn, compiled_sql, distilled_params)
        return rv

    @util.memoized_property
    def return_model(self):
        # noinspection PyUnresolvedReferences
        return self.execution_options.get('return_model', True)

    @util.memoized_property
    def model(self):
        # noinspection PyUnresolvedReferences
        rv = self.execution_options.get('model', None)
        if isinstance(rv, weakref.ref):
            rv = rv()
        return rv

    @util.memoized_property
    def timeout(self):
        # noinspection PyUnresolvedReferences
        return self.execution_options.get('timeout', None)

    def from_row(self, row, return_row=False):
        if self.model is None or row is None:
            return row
        for index, (key, value) in enumerate(row.items()):
            type_ = getattr(getattr(self.model, key), 'type', None)
            if type_ is not None:
                processor = self.get_result_processor(type_, None, None)
                if processor:
                    new_value = processor(value)
                    if new_value is not value:
                        update_record(row, index, new_value)
        if not return_row and self.return_model:
            rv = self.model()
            rv.__values__.update(row)
        else:
            rv = row
        return rv


class GinoCursorFactory:
    def __init__(self, env_factory, clause, multiparams, params):
        self._env_factory = env_factory
        self._context = None
        self._timeout = None
        self._clause = clause
        self._multiparams = multiparams
        self._params = params

    @property
    def timeout(self):
        return self._timeout

    async def get_cursor_factory(self):
        connection, metadata = self._env_factory()
        self._context = metadata.dialect.execution_ctx_cls.init_clause(
            metadata.dialect, self._clause, self._multiparams, self._params,
            getattr(connection, 'execution_options', None))
        self._timeout = self._context.timeout
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

    async def many(self, n, *, timeout=DEFAULT):
        if timeout is DEFAULT:
            timeout = self._factory.timeout
        rows = await self._cursor.fetch(n, timeout=timeout)
        return list(map(self._factory.context.from_row, rows))

    async def next(self, *, timeout=DEFAULT):
        if timeout is DEFAULT:
            timeout = self._factory.timeout
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
            self, elem, multiparams, params, None)
        return context.statement, context.parameters[0]

    async def do_all(self, bind, clause, *multiparams, **params):
        context = self.execution_ctx_cls.init_clause(
            self, clause, multiparams, params,
            getattr(bind, 'execution_options', None))
        rows = await bind.fetch(context.statement, *context.parameters[0],
                                timeout=context.timeout)
        return list(map(context.from_row, rows))

    async def do_first(self, bind, clause, *multiparams, **params):
        context = self.execution_ctx_cls.init_clause(
            self, clause, multiparams, params,
            getattr(bind, 'execution_options', None))
        row = await bind.fetchrow(context.statement, *context.parameters[0],
                                  timeout=context.timeout)
        return context.from_row(row)

    async def do_scalar(self, bind, clause, *multiparams, **params):
        context = self.execution_ctx_cls.init_clause(
            self, clause, multiparams, params,
            getattr(bind, 'execution_options', None))
        row = await bind.fetchrow(context.statement, *context.parameters[0],
                                  timeout=context.timeout)
        if not row:
            return None
        return next(iter(context.from_row(row, return_row=True).values()))

    async def do_status(self, bind, clause, *multiparams, **params):
        context = self.execution_ctx_cls.init_clause(
            self, clause, multiparams, params,
            getattr(bind, 'execution_options', None))
        return await bind.execute(context.statement, *context.parameters[0],
                                  timeout=context.timeout)
