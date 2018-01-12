import asyncio

from sqlalchemy.engine import Connection as SAConnection

from .utils import Deferred
from .exceptions import InterfaceError
from .result import AsyncResultProxy


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


class Transaction:
    def __init__(self, sa_conn, args, kwargs):
        self._sa_conn = sa_conn
        self._args = args
        self._kwargs = kwargs
        self._transaction = Deferred(self._new_transaction())

    async def _new_transaction(self):
        conn = await self._sa_conn.connection()
        return conn.transaction(*self._args, **self._kwargs)

    async def __aenter__(self):
        tx = await self._transaction
        return await tx.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        tx = await self._transaction
        return await tx.__aexit__(exc_type, exc_val, exc_tb)

    async def start(self):
        tx = await self._transaction
        return await tx.start()

    async def commit(self):
        tx = await self._transaction
        return await tx.commit()

    async def rollback(self):
        tx = await self._transaction
        return await tx.rollback()

    def __repr__(self):
        try:
            rv = repr(self._transaction.result())
        except (asyncio.InvalidStateError, AttributeError):
            rv = 'pending'
        except asyncio.CancelledError:
            rv = 'cancelled'
        return f'<gino.connection.Transaction {rv}>'


# noinspection PyAbstractClass
class SAConnectionAdaptor(SAConnection):
    def __init__(self, conn):
        self._conn = conn
        super().__init__(getattr(getattr(conn, '_engine'), '_sa_engine'), conn)

    async def __aenter__(self):
        return self, await getattr(self._conn, '_get_conn')()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def _branch(self):
        return self


class Connection(SAConnection):
    _deferred = None

    @property
    def deferred(self):
        coro, self._deferred = self._deferred, None
        return coro

    @deferred.setter
    def deferred(self, val):
        assert self._deferred is None
        self._deferred = val

    def _clone(self):
        rv = super()._clone()
        rv._deferred = None
        return rv

    def __enter__(self):
        raise NotImplementedError('Please use `async with` instead')

    def __exit__(self, exc_type, exc_val, exc_tb):
        raise NotImplementedError('Please use `async with` instead')

    async def __aenter__(self):
        await self.connection()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def __await__(self):
        return self.__aenter__().__await__()

    async def execution_options(self, **opt):
        rv = super().execution_options(**opt)
        await rv.deferred
        return rv

    async def connection(self):
        try:
            coro = self.__connection
        except AttributeError:
            try:
                return await self._revalidate_connection()
            except BaseException as e:
                await self._handle_dbapi_exception(e, None, None, None, None)
        else:
            return await coro

    async def get_isolation_level(self):
        try:
            return await self.dialect.get_isolation_level(
                await self.connection())
        except BaseException as e:
            await self._handle_dbapi_exception(e, None, None, None, None)

    async def info(self):
        return (await self.connection()).info

    def contextual_connect(self, close_with_result=False):
        rv = super().contextual_connect()
        rv.should_close_with_result = close_with_result
        return rv

    def begin(self, *args, **kwargs):
        return Transaction(self, args, kwargs)

    def _execute_context(self, dialect, constructor,
                         statement, parameters, *args):
        return AsyncResultProxy(
            dialect, self, constructor, statement, parameters, args,
            auto_close_connection=self.should_close_with_result)

    async def close(self):
        if self.__branch_from:
            try:
                del self.__connection
            except AttributeError:
                pass
            finally:
                self.__can_reconnect = False
                return
        try:
            conn = await self.__connection
        except AttributeError:
            pass
        else:
            await conn.close()
            if conn._reset_agent is self.__transaction:
                conn._reset_agent = None

            # the close() process can end up invalidating us,
            # as the pool will call our transaction as the "reset_agent"
            # for rollback(), which can then cause an invalidation
            if not self.__invalid:
                del self.__connection
        self.__can_reconnect = False
        self.__transaction = None

    # async def release(self, *, close=False):
    #     if self._root is self:
    #         fut, self._future = self._future, not close
    #         if not isinstance(fut, bool):
    #             await getattr(self._engine, '_release')(await fut)

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

    def create(self, entity, **kwargs):
        pass

    def drop(self, entity, **kwargs):
        pass
