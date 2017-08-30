import sys
import weakref

import sqlalchemy as sa
from sqlalchemy.sql.base import Executable
from sqlalchemy.dialects import postgresql as sa_pg

from .connection import GinoConnection
from .crud import CRUDModel
from .declarative import declarative_base
from .dialect import AsyncpgDialect, GinoCursorFactory
from .pool import GinoPool
from . import json_support


class GinoTransaction:
    __slots__ = ('_conn_ctx', '_isolation', '_readonly', '_deferrable', '_ctx')

    def __init__(self, conn_ctx, isolation, readonly, deferrable):
        self._conn_ctx = conn_ctx
        self._isolation = isolation
        self._readonly = readonly
        self._deferrable = deferrable
        self._ctx = None

    async def __aenter__(self):
        conn = await self._conn_ctx.__aenter__()
        self._ctx = conn.transaction(isolation=self._isolation,
                                     readonly=self._readonly,
                                     deferrable=self._deferrable)
        return conn, await self._ctx.__aenter__()

    async def __aexit__(self, extype, ex, tb):
        try:
            await self._ctx.__aexit__(extype, ex, tb)
        except:
            await self._conn_ctx.__aexit__(*sys.exc_info())
            raise
        else:
            await self._conn_ctx.__aexit__(extype, ex, tb)


class ConnectionAcquireContext:
    __slots__ = ('_connection',)

    def __init__(self, connection):
        self._connection = connection

    async def __aenter__(self):
        return self._connection

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def __await__(self):
        return self

    def __next__(self):
        raise StopIteration(self._connection)


class GinoExecutor:
    __slots__ = ('_query',)

    def __init__(self, query):
        self._query = query

    @property
    def query(self):
        return self._query

    def model(self, model):
        self._query = self._query.execution_options(model=weakref.ref(model))
        return self

    def return_model(self, switch):
        self._query = self._query.execution_options(return_model=switch)
        return self

    def timeout(self, timeout):
        self._query = self._query.execution_options(timeout)
        return self

    def get_bind(self, bind):
        return bind or self._query.bind

    async def all(self, *multiparams, bind=None, **params):
        bind = self.get_bind(bind)
        return await bind.metadata.dialect.do_all(
            bind, self._query, *multiparams, **params)

    async def first(self, *multiparams, bind=None, **params):
        bind = self.get_bind(bind)
        return await bind.metadata.dialect.do_first(
            bind, self._query, *multiparams, **params)

    async def scalar(self, *multiparams, bind=None, **params):
        bind = self.get_bind(bind)
        return await bind.metadata.dialect.do_scalar(
            bind, self._query, *multiparams, **params)

    async def status(self, *multiparams, bind=None, **params):
        """
        You can parse the return value like this: https://git.io/v7oze
        """
        bind = self.get_bind(bind)
        return await bind.metadata.dialect.do_status(
            bind, self._query, *multiparams, **params)

    def iterate(self, *multiparams, connection=None, **params):
        def env_factory():
            conn = self.get_bind(connection)
            return conn, conn.metadata
        return GinoCursorFactory(env_factory, self._query, multiparams, params)


class Gino(sa.MetaData):
    default_model_classes = (CRUDModel,)

    def __init__(self, bind=None, dialect=None, model_classes=None,
                 query_ext=True, **kwargs):
        self._bind = None
        super().__init__(bind=bind, **kwargs)
        self.dialect = dialect or AsyncpgDialect()
        if model_classes is None:
            model_classes = self.default_model_classes
        self.Model = declarative_base(self, model_classes)
        for mod in sa, sa_pg, json_support:
            for key in mod.__all__:
                if not hasattr(self, key):
                    setattr(self, key, getattr(mod, key))
        if query_ext:
            Executable.gino = property(GinoExecutor)

    @property
    def bind(self):
        return getattr(self._bind, 'get_current_connection',
                       lambda: None)() or self._bind

    # noinspection PyMethodOverriding
    @bind.setter
    def bind(self, val):
        self._bind = val

    def create_pool(self, dsn=None, *,
                    min_size=10,
                    max_size=10,
                    max_queries=50000,
                    max_inactive_connection_lifetime=300.0,
                    setup=None,
                    init=None,
                    loop=None,
                    connection_class=GinoConnection,
                    **connect_kwargs):
        if not issubclass(connection_class, GinoConnection):
            raise TypeError(
                'connection_class is expected to be a subclass of '
                'gino.GinoConnection, got {!r}'.format(connection_class))

        pool = GinoPool(
            self, dsn,
            connection_class=connection_class,
            min_size=min_size, max_size=max_size,
            max_queries=max_queries, loop=loop, setup=setup, init=init,
            max_inactive_connection_lifetime=max_inactive_connection_lifetime,
            **connect_kwargs)
        return pool

    def compile(self, elem, *multiparams, **params):
        return self.dialect.compile(elem, *multiparams, **params)

    async def all(self, clause, *multiparams, bind=None, **params):
        return await self.dialect.do_all(
            bind or self.bind, clause, *multiparams, **params)

    async def first(self, clause, *multiparams, bind=None, **params):
        return await self.dialect.do_first(
            bind or self.bind, clause, *multiparams, **params)

    async def scalar(self, clause, *multiparams, bind=None, **params):
        return await self.dialect.do_scalar(
            bind or self.bind, clause, *multiparams, **params)

    async def status(self, clause, *multiparams, bind=None, **params):
        return await self.dialect.do_status(
            bind or self.bind, clause, *multiparams, **params)

    def iterate(self, clause, *multiparams, connection=None, **params):
        return GinoCursorFactory(lambda: (connection or self.bind, self),
                                 clause, multiparams, params)

    def acquire(self, *, timeout=None, reuse=True, lazy=False):
        method = getattr(self._bind, 'acquire', None)
        if method is None:
            return ConnectionAcquireContext(self._bind)
        else:
            return method(timeout=timeout, reuse=reuse, lazy=lazy)

    def transaction(self, *, isolation='read_committed', readonly=False,
                    deferrable=False, timeout=None, reuse=True):
        return GinoTransaction(self.acquire(timeout=timeout, reuse=reuse),
                               isolation, readonly, deferrable)
