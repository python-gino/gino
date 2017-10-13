class Database:
    async def acquire(self, kwargs):
        pass

    async def release(self, conn):
        pass


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
        self._cursor = DBAPICursorAdaptor(conn)

    def cursor(self):
        return self._cursor


class AsyncResultProxy:
    def __init__(self, dialect, connection_factory, constructor, statement,
                 parameters, args):
        self._dialect = dialect
        self._connection_factory = connection_factory
        self._constructor = constructor
        self._statement = statement
        self._parameters = parameters
        self._args = args

        self._context = None
        self._proxy = None
        self._buffer = None

    async def _prepare(self, sa_conn, conn):
        conn = DBAPIConnectionAdaptor(conn)
        self._context = await self._constructor(self._dialect, sa_conn, conn,
                                                *self._args)
        self._proxy = self._context.get_result_proxy()

    def process_rows(self, rows, return_model=True):
        context = self._context
        rv = rows = self._proxy.process_rows(rows)
        if context.model is not None and return_model and context.return_model:
            rv = []
            for row in rows:
                obj = context.model()
                obj.__values__.update(row)
                rv.append(obj)
        return rv

    async def _execute(self):
        with self._connection_factory as (sa_conn, conn):
            await self._prepare(sa_conn, conn)
            self.all()

    def __await__(self):
        return self._execute().__await__()

    async def first(self):
        row = await self._cursor.fetchrow(*self._context.parameters[0])
        if not row:
            return row
        return self.process_rows([row])[0]

    async def scalar(self, column=0):
        return await self._cursor.fetchval(*self._context.parameters[0],
                                           column=column)

    async def all(self):
        rows = await self._cursor.fetch(*self._context.parameters[0])
        return self.process_rows(rows)

    async def buffer_all(self):
        self._buffer = await self.all()
        self._cursor.get_statusmsg()


class AsyncDialectMixin:
    def get_async_result_proxy(self, *args):
        return AsyncResultProxy(self, *args)
