import asyncio

from ..result import AsyncResultProxy


class Pool:
    def __init__(self, creator, dialect=None, loop=None):
        self.url = creator()
        self.dialect = dialect
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop

    async def init(self):
        raise NotImplementedError

    async def release(self, conn):
        raise NotImplementedError

    # sa.Pool APIs

    async def unique_connection(self):
        raise NotImplementedError

    async def connect(self):
        return await self.unique_connection()


class DBAPICursorAdaptor:
    def __init__(self, conn):
        self._conn = conn
        self._stmt = None

    @property
    def description(self):
        try:
            return [((a[0], a[1][0]) + (None,) * 5)
                    for a in self._stmt.get_attributes()]
        except TypeError:  # asyncpg <= 0.12.0
            return []

    def __getattr__(self, item):
        return getattr(self._stmt, item)

    async def prepare(self, stat):
        self._stmt = await self._conn.prepare(stat)


class DBAPIConnectionAdaptor:
    def __init__(self, conn):
        self._conn = conn
        self._cursor = DBAPICursorAdaptor(conn)

    def cursor(self):
        return self._cursor


class DBAPIAdaptor:
    paramstyle = 'numeric'
    Error = Exception

    @classmethod
    def connect(cls, url):
        return url


class AsyncDialectMixin:
    dbapi_class = DBAPIAdaptor

    @classmethod
    def dbapi(cls):
        return cls.dbapi_class

    def get_async_result_proxy(self, *args):
        return AsyncResultProxy(self, *args)
