import weakref

from asyncpg.prepared_stmt import PreparedStatement
from sqlalchemy import util
# noinspection PyProtectedMember
from sqlalchemy.engine.util import _distill_params
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.dialects.postgresql.base import (
    PGCompiler,
    PGDialect,
    PGExecutionContext,
)
from .pool import LazyConnection

DEFAULT = object()


class AsyncpgCompiler(PGCompiler):
    @property
    def bindtemplate(self):
        return self._bindtemplate

    @bindtemplate.setter
    def bindtemplate(self, val):
        # noinspection PyAttributeOutsideInit
        self._bindtemplate = val.replace(':', '$')


class AnonymousPreparedStatement(PreparedStatement):
    def __del__(self):
        self._state.detach()


class ConnectionAdaptor:
    __slots__ = ('_dialect', '_conn', '_opts', '_stmt', '_echo')

    def __init__(self, dialect, connection, compiled_sql):
        self._dialect = dialect
        self._conn = connection
        self._opts = dict(getattr(connection, 'execution_options', {}))
        for opt in ('return_model', 'model', 'timeout'):
            if opt in compiled_sql.execution_options:
                self._opts.pop(opt, None)
        self._stmt = None
        self._echo = False

    def cursor(self):
        return self

    @property
    def dialect(self):
        return self._dialect

    @property
    def _execution_options(self):
        return self._opts

    @property
    def description(self):
        try:
            return [((a[0], a[1][0]) + (None,) * 5)
                    for a in self._stmt.get_attributes()]
        except TypeError:  # asyncpg <= 0.12.0
            return []

    def _branch(self):
        return self

    async def prepare(self, statement, named=True):
        if named:
            rv = await self._conn.prepare(statement)
        else:
            # it may still be a named statement, if cache is not disabled
            # noinspection PyProtectedMember
            self._conn._check_open()
            # noinspection PyProtectedMember
            state = await self._conn._get_statement(statement, None)
            if state.name:
                rv = PreparedStatement(self._conn, statement, state)
            else:
                rv = AnonymousPreparedStatement(self._conn, statement, state)
        self._stmt = rv
        return rv


# noinspection PyAbstractClass
class AsyncpgExecutionContext(PGExecutionContext):
    @classmethod
    def init_clause(cls, dialect, elem, multiparams, params, connection):
        # partially copied from:
        # sqlalchemy.engine.base.Connection:_execute_clauseelement
        distilled_params = _distill_params(multiparams, params)
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
        conn = ConnectionAdaptor(dialect, connection, compiled_sql)
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

    def process_rows(self, rows, return_model=True):
        rv = rows = self.get_result_proxy().process_rows(rows)
        if self.model is not None and return_model and self.return_model:
            rv = []
            for row in rows:
                obj = self.model()
                obj.__values__.update(row)
                rv.append(obj)
        return rv

    async def prepare(self, named=True):
        return await self.connection.prepare(self.statement, named)


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
            connection)
        if self._context.executemany:
            raise ValueError('too many multiparams')
        self._timeout = self._context.timeout
        ps = await self._context.prepare()
        return ps.cursor(*self._context.parameters[0], timeout=self._timeout)

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
        return self._factory.context.process_rows([row])[0]


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
        return self._factory.context.process_rows(rows)

    async def next(self, *, timeout=DEFAULT):
        if timeout is DEFAULT:
            timeout = self._factory.timeout
        row = await self._cursor.fetchrow(timeout=timeout)
        return self._factory.context.process_rows([row])[0]

    def __getattr__(self, item):
        return getattr(self._cursor, item)


# noinspection PyAbstractClass
class AsyncpgDialect(PGDialect):
    driver = 'asyncpg'
    supports_native_decimal = True
    default_paramstyle = 'numeric'
    statement_compiler = AsyncpgCompiler
    execution_ctx_cls = AsyncpgExecutionContext
    dbapi_type_map = {
        114: JSON(),
        3802: JSONB(),
    }

    def compile(self, elem, *multiparams, **params):
        context = self.execution_ctx_cls.init_clause(
            self, elem, multiparams, params, None)
        if context.executemany:
            return context.statement, context.parameters
        else:
            return context.statement, context.parameters[0]

    async def _execute_clauseelement(self, connection, clause, multiparams,
                                     params, many=False, status=False,
                                     return_model=True):
        context = self.execution_ctx_cls.init_clause(
            self, clause, multiparams, params, connection)
        if context.executemany and not many:
            raise ValueError('too many multiparams')
        # noinspection PyProtectedMember
        if isinstance(connection, LazyConnection):
            await connection.get_connection()
        with connection._stmt_exclusive_section:
            prepared = await context.prepare(named=False)
            rv = []
            for args in context.parameters:
                rows = await prepared.fetch(*args, timeout=context.timeout)
                item = context.process_rows(rows, return_model=return_model)
                if status:
                    item = prepared.get_statusmsg(), item
                if not many:
                    return item
                rv.append(item)
            return rv

    async def do_all(self, connection, clause, *multiparams, **params):
        return await self._execute_clauseelement(
            connection, clause, multiparams, params)

    async def do_first(self, connection, clause, *multiparams, **params):
        items = await self._execute_clauseelement(
            connection, clause, multiparams, params)
        if not items:
            return None
        return items[0]

    async def do_scalar(self, connection, clause, *multiparams, **params):
        items = await self._execute_clauseelement(
            connection, clause, multiparams, params, return_model=False)
        if not items:
            return None
        return items[0][0]

    async def do_status(self, connection, clause, *multiparams, **params):
        return (await self._execute_clauseelement(
            connection, clause, multiparams, params, status=True))[0]
