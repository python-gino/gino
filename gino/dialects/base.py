import weakref

from sqlalchemy import util

# noinspection PyProtectedMember
from ..engine import _SAConnection, _SAEngine, _DBAPIConnection

DEFAULT = object()


class DBAPICursor:
    def execute(self, statement, parameters):
        pass

    def executemany(self, statement, parameters):
        pass

    @property
    def description(self):
        raise NotImplementedError

    async def prepare(self, query, timeout):
        raise NotImplementedError

    async def async_execute(self, query, timeout, args, limit=0, many=False):
        raise NotImplementedError

    def get_statusmsg(self):
        raise NotImplementedError


class Pool:
    @property
    def raw_pool(self):
        raise NotImplementedError

    async def acquire(self, *, timeout=None):
        raise NotImplementedError

    async def release(self, conn):
        raise NotImplementedError

    async def close(self):
        raise NotImplementedError


class Transaction:
    @property
    def raw_transaction(self):
        raise NotImplementedError

    async def begin(self):
        raise NotImplementedError

    async def commit(self):
        raise NotImplementedError

    async def rollback(self):
        raise NotImplementedError


class PreparedStatement:
    def __init__(self):
        self.context = None

    def iterate(self, *params, **kwargs):
        return _PreparedIterableCursor(self, params, kwargs)

    def _get_iterator(self, *params, **kwargs):
        raise NotImplementedError

    async def _get_cursor(self, *params, **kwargs):
        raise NotImplementedError


class _PreparedIterableCursor:
    def __init__(self, prepared, params, kwargs):
        self._prepared = prepared
        self._params = params
        self._kwargs = kwargs

    def __aiter__(self):
        return getattr(self._prepared, '_get_iterator')(*self._params,
                                                        **self._kwargs)

    def __await__(self):
        return getattr(self._prepared, '_get_cursor')(
            *self._params, **self._kwargs).__await__()


class _IterableCursor:
    def __init__(self, context):
        self._context = context

    async def _iterate(self):
        prepared = await self._context.cursor.prepare(self._context.statement,
                                                      self._context.timeout)
        prepared.context = self._context
        return prepared.iterate(*self._context.parameters[0],
                                timeout=self._context.timeout)

    async def _get_cursor(self):
        return await (await self._iterate())

    def __aiter__(self):
        return _LazyIterator(self._iterate)

    def __await__(self):
        return self._get_cursor().__await__()


class _LazyIterator:
    def __init__(self, init):
        self._init = init
        self._iter = None

    async def __anext__(self):
        if self._iter is None:
            self._iter = (await self._init()).__aiter__()
        return await self._iter.__anext__()


class _ResultProxy:
    _metadata = True

    def __init__(self, context):
        self._context = context

    @property
    def context(self):
        return self._context

    async def execute(self, one=False, return_model=True, status=False):
        context = self._context
        cursor = context.cursor
        if context.executemany:
            return await cursor.async_execute(
                context.statement, context.timeout, context.parameters,
                many=True)
        else:
            args = context.parameters[0]
            rows = await cursor.async_execute(
                context.statement, context.timeout, args, 1 if one else 0)
            item = context.process_rows(rows, return_model=return_model)
            if one:
                if item:
                    item = item[0]
                else:
                    item = None
            if status:
                item = cursor.get_statusmsg(), item
            return item

    def iterate(self):
        if self._context.executemany:
            raise ValueError('too many multiparams')
        return _IterableCursor(self._context)

    def _soft_close(self):
        pass


class Cursor:
    async def many(self, n, *, timeout=DEFAULT):
        raise NotImplementedError

    async def next(self, *, timeout=DEFAULT):
        raise NotImplementedError

    async def forward(self, n, *, timeout=DEFAULT):
        raise NotImplementedError


class ExecutionContextOverride:
    def _compiled_first_opt(self, key, default=DEFAULT):
        rv = DEFAULT
        opts = getattr(getattr(self, 'compiled', None), 'execution_options',
                       None)
        if opts:
            rv = opts.get(key, DEFAULT)
        if rv is DEFAULT:
            # noinspection PyUnresolvedReferences
            rv = self.execution_options.get(key, default)
        if rv is DEFAULT:
            raise LookupError('No such execution option!')
        return rv

    @util.memoized_property
    def return_model(self):
        return self._compiled_first_opt('return_model', True)

    @util.memoized_property
    def model(self):
        rv = self._compiled_first_opt('model', None)
        if isinstance(rv, weakref.ref):
            rv = rv()
        return rv

    @util.memoized_property
    def timeout(self):
        return self._compiled_first_opt('timeout', None)

    def process_rows(self, rows, return_model=True):
        # noinspection PyUnresolvedReferences
        rv = rows = super().get_result_proxy().process_rows(rows)
        if self.model is not None and return_model and self.return_model:
            rv = []
            for row in rows:
                obj = self.model()
                obj.__values__.update(row)
                rv.append(obj)
        return rv

    def get_result_proxy(self):
        return _ResultProxy(self)


class AsyncDialectMixin:
    cursor_cls = DBAPICursor

    def _init_mixin(self):
        self._sa_conn = _SAConnection(
            _SAEngine(self), _DBAPIConnection(self.cursor_cls))

    def compile(self, elem, *multiparams, **params):
        context = self._sa_conn.execute(elem, *multiparams, **params).context
        if context.executemany:
            return context.statement, context.parameters
        else:
            return context.statement, context.parameters[0]

    async def init_pool(self, url, loop):
        raise NotImplementedError

    def transaction(self, raw_conn, args, kwargs):
        raise NotImplementedError
