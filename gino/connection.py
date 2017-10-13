import asyncio

from sqlalchemy.engine import Connection as SAConnection

from .exceptions import InterfaceError


class AwaitableCallable:
    def __init__(self, execution, item):
        self._execution = execution
        self._item = item

    async def get(self):
        await self._execution._async_init()
        return getattr(self._execution._result, self._item)

    # def __await__(self):
    #     return self.get().__await__()

    async def __call__(self, *args, **kwargs):
        # noinspection PyCallingNonCallable
        return await (await self.get())(*args, **kwargs)


class AsyncExecution:
    def __init__(self, sa_conn, dialect, constructor, args):
        self._sa_conn = sa_conn
        self._dialect = dialect
        self._constructor = constructor
        self._args = args

    async def _execute(self):
        conn = await self._sa_conn.get_dbapi_conn()
        context = await self._constructor(self._dialect, self._sa_conn, conn,
                                          *self._args)
        return context.get_async_result_proxy()

    async def _get_result_proxy(self):
        rv = await self._execute()
        await rv.buffer_all()
        await self._async_init()
        return context.get_async_result_proxy()
        return self._result

    def __await__(self):
        return self._get_result_proxy().__await__()

    def __getattr__(self, item):
        return AwaitableCallable(self, item)


# noinspection PyAbstractClass
class SAConnectionAdaptor(SAConnection):
    def __init__(self, conn):
        self._conn = conn
        super().__init__(getattr(getattr(conn, '_engine'), '_sa_engine'), conn)

    async def __aenter__(self):
        return self, await getattr(self._conn, '_get_conn')()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def _execute_context(self, dialect, constructor,
                         statement, parameters, *args):
        return dialect.get_async_result_proxy(self, constructor, statement,
                                              parameters, args)

    def _branch(self):
        return self


class Connection:
    def __init__(self, engine, kwargs, root=None, loop=None):
        if root is None:
            root = self
        if loop is None:
            loop = asyncio.get_event_loop()

        self._engine = engine
        self._kwargs = kwargs
        self._root = root
        self._loop = loop

        self._future = True
        self._sa_conn = SAConnectionAdaptor(self)

    def execute(self, obj, *multiparams, **params):
        return self._sa_conn.execute(obj, *multiparams, **params)

    async def release(self, *, close=False):
        if self._root is self:
            fut, self._future = self._future, not close
            if not isinstance(fut, bool):
                await getattr(self._engine, '_release')(await fut)

    async def _get_conn(self):
        if self._root is self:
            awaitable = self._future
            if awaitable is False:
                raise InterfaceError('the connection is already closed')
            elif awaitable is True:
                awaitable = self._future = self._loop.create_task(
                    getattr(self._engine, '_acquire')(self._kwargs))
        else:
            awaitable = self._root._get_conn()
        return await awaitable

    def _execute_clauseelement(self, elem, multiparams, params):
        return self._sa_conn._execute_clauseelement(elem, multiparams, params)
