import weakref

import sqlalchemy as sa
from sqlalchemy.sql.base import Executable
from sqlalchemy.dialects import postgresql as sa_pg

from .crud import CRUDModel
from .declarative import declarative_base
from .dialects.asyncpg import GinoCursorFactory
from . import json_support


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

    async def all(self, *multiparams, bind=None, **params):
        if bind is None:
            bind = self._query.bind
        return await bind.all(self._query, *multiparams, **params)

    async def first(self, *multiparams, bind=None, **params):
        if bind is None:
            bind = self._query.bind
        return await bind.first(self._query, *multiparams, **params)

    async def scalar(self, *multiparams, bind=None, **params):
        if bind is None:
            bind = self._query.bind
        return await bind.scalar(self._query, *multiparams, **params)

    async def status(self, *multiparams, bind=None, **params):
        if bind is None:
            bind = self._query.bind
        return await bind.status(self._query, *multiparams, **params)

    def iterate(self, *multiparams, connection=None, **params):
        def env_factory():
            conn = connection or self._query.bind
            return conn, conn.metadata
        return GinoCursorFactory(env_factory, self._query, multiparams, params)


class Gino(sa.MetaData):
    model_base_classes = (CRUDModel,)
    query_executor = GinoExecutor

    def __init__(self, bind=None, model_classes=None,
                 query_ext=True, **kwargs):
        super().__init__(bind=bind, **kwargs)
        if model_classes is None:
            model_classes = self.model_base_classes
        self.Model = declarative_base(self, model_classes)
        for mod in json_support, sa_pg, sa:
            for key in mod.__all__:
                if not hasattr(self, key):
                    setattr(self, key, getattr(mod, key))
        if query_ext:
            Executable.gino = property(self.query_executor)

    async def create_engine(self, name_or_url, loop=None, **kwargs):
        from .strategies import create_engine
        e = await create_engine(name_or_url, loop=loop, **kwargs)
        self.bind = e
        return e

    async def dispose_engine(self):
        if self.bind is not None:
            bind, self.bind = self.bind, None
            await bind.close()

    def compile(self, elem, *multiparams, **params):
        return self.bind.compile(elem, *multiparams, **params)

    async def all(self, clause, *multiparams, **params):
        return await self.bind.all(clause, *multiparams, **params)

    async def first(self, clause, *multiparams, **params):
        return await self.bind.first(clause, *multiparams, **params)

    async def scalar(self, clause, *multiparams, **params):
        return await self.bind.scalar(clause, *multiparams, **params)

    async def status(self, clause, *multiparams, **params):
        return await self.bind.status(clause, *multiparams, **params)

    def iterate(self, clause, *multiparams, connection=None, **params):
        return GinoCursorFactory(lambda: (connection or self.bind, self),
                                 clause, multiparams, params)

    def acquire(self, *args, **kwargs):
        return self.bind.acquire(*args, **kwargs)

    def transaction(self, *args, **kwargs):
        return self.bind.transaction(*args, **kwargs)
