import asyncio
import weakref

from sqlalchemy import util
from sqlalchemy.events import PoolEvents

from ..utils import Deferred


class DBAPICursorAdaptor:
    def __init__(self, conn):
        self._conn = conn

    @property
    def description(self):
        return self._conn.get_description()

    def __getattr__(self, item):
        return getattr(self._stmt, item)


class DBAPIConnectionAdaptor:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return DBAPICursorAdaptor(self)

    async def prepare(self, statement):
        raise NotImplementedError

    async def first(self, *params):
        raise NotImplementedError

    async def scalar(self, *params):
        raise NotImplementedError

    async def all(self, *params):
        raise NotImplementedError

    def get_description(self):
        raise NotImplementedError


class Pool:
    adaptor = DBAPIConnectionAdaptor

    def __init__(self, creator, dialect=None, loop=None):
        self._args, self._kwargs = creator()
        self.dialect = dialect
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self._init_done = Deferred(self._init())

    # noinspection PyUnusedLocal
    def __init_subclass__(cls, **kwargs):
        class NewPoolEvents(PoolEvents):
            _dispatch_target = cls

    def __await__(self):
        return self._init_done.__await__()

    async def _init(self):
        raise NotImplementedError

    async def _acquire(self):
        raise NotImplementedError

    async def _release(self, conn):
        raise NotImplementedError

    # sa.Pool APIs

    async def unique_connection(self):
        await self._init_done
        return self.adaptor(await self._acquire())

    async def connect(self):
        return await self.unique_connection()


class DBAPIAdaptor:
    paramstyle = 'numeric'
    Error = Exception

    @classmethod
    def connect(cls, *args, **kwargs):
        return args, kwargs


class AsyncDialectMixin:
    dbapi_class = DBAPIAdaptor

    @classmethod
    def dbapi(cls):
        return cls.dbapi_class


class ExecutionContextMixin:
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
