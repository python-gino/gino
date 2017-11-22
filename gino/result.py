from .utils import Deferred


class AsyncResultProxy:
    def __init__(self, dialect, connection, constructor, statement,
                 parameters, args):
        self._dialect = dialect
        self._connection = connection
        self._constructor = constructor
        self._statement = statement
        self._parameters = parameters
        self._args = args

        self._context = None
        self._conn = None
        self._proxy = None
        self._preparation = Deferred(self._prepare())
        # self._buffer = None

    async def _prepare(self):
        self._conn = await self._connection.get_dbapi_connection()
        self._context = self._constructor(
            self._dialect, self._connection, self._conn, *self._args)
        await self._conn.prepare(self._context.statement)
        self._proxy = self._context.get_result_proxy()

    def _process_rows(self, rows, return_model=True):
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
        await self._preparation
        return await self.all()

    def __await__(self):
        return self._execute().__await__()

    async def first(self):
        await self._preparation
        row = await self._conn.first(*self._context.parameters[0])
        if not row:
            return row
        return self._process_rows([row])[0]

    async def scalar(self):
        await self._preparation
        return await self._conn.scalar(*self._context.parameters[0])

    async def all(self):
        rows = await self._conn.all(*self._context.parameters[0])
        return self._process_rows(rows)

    # async def buffer_all(self):
    #     self._buffer = await self.all()
    #     self._cursor.get_statusmsg()
