import weakref

import sqlalchemy as sa
from sqlalchemy.engine.url import make_url, URL
from sqlalchemy.sql.base import Executable
from sqlalchemy.dialects import postgresql as sa_pg
from sqlalchemy.sql.schema import SchemaItem

from .crud import CRUDModel
from .declarative import declarative_base
from .schema import GinoSchemaVisitor
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

    async def all(self, *multiparams, **params):
        return await self._query.bind.all(self._query, *multiparams, **params)

    async def first(self, *multiparams, **params):
        return await self._query.bind.first(self._query, *multiparams,
                                            **params)

    async def scalar(self, *multiparams, **params):
        return await self._query.bind.scalar(self._query, *multiparams,
                                             **params)

    async def status(self, *multiparams, **params):
        return await self._query.bind.status(self._query, *multiparams,
                                             **params)

    def iterate(self, *multiparams, **params):
        connection = self._query.bind.current_connection
        if connection is None:
            raise ValueError(
                'No Connection in context, please provide one')
        return connection.iterate(self._query, *multiparams, **params)


class Gino(sa.MetaData):
    model_base_classes = (CRUDModel,)
    query_executor = GinoExecutor
    schema_visitor = GinoSchemaVisitor

    def __init__(self, bind=None, model_classes=None, **kwargs):
        super().__init__(bind=bind, **kwargs)
        if model_classes is None:
            model_classes = self.model_base_classes
        self.Model = declarative_base(self, model_classes)
        for mod in json_support, sa_pg, sa:
            for key in mod.__all__:
                if not hasattr(self, key):
                    setattr(self, key, getattr(mod, key))

    @property
    def bind(self):
        return self._bind

    # noinspection PyMethodOverriding,PyAttributeOutsideInit
    @bind.setter
    def bind(self, bind):
        self._bind = bind
        if bind is None:
            for ext in Executable, SchemaItem:
                if hasattr(ext, 'gino'):
                    delattr(ext, 'gino')
        else:
            Executable.gino = property(self.query_executor)
            SchemaItem.gino = property(self.schema_visitor)

    async def set_bind(self, bind, loop=None, **kwargs):
        if isinstance(bind, str):
            bind = make_url(bind)
        if isinstance(bind, URL):
            from .strategies import create_engine
            bind = await create_engine(bind, loop=loop, **kwargs)
        self.bind = bind
        return bind

    def pop_bind(self):
        bind, self.bind = self.bind, None
        return bind

    def __await__(self):
        async def init():
            await self.set_bind(self.bind)
            return self
        return init().__await__()

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

    def iterate(self, clause, *multiparams, **params):
        connection = getattr(self.bind, 'current_connection', None)
        if connection is None:
            raise ValueError(
                'No Connection in context, please provide one')
        return connection.iterate(clause, *multiparams, **params)

    def acquire(self, *args, **kwargs):
        return self.bind.acquire(*args, **kwargs)

    def transaction(self, *args, **kwargs):
        return self.bind.transaction(*args, **kwargs)
