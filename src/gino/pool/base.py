from logging import Logger

from sqlalchemy import event, util, exc
from sqlalchemy import log
from sqlalchemy.exc import InvalidRequestError


class AsyncPool(log.Identified):
    logger: Logger

    def __init__(
        self,
        creator,
        recycle=-1,
        echo=None,
        logging_name=None,
        reset_on_return=True,
        events=None,
        dialect=None,
        pre_ping=False,
        _dispatch=None,
    ):
        if logging_name:
            self.logging_name = self._orig_logging_name = logging_name
        else:
            self._orig_logging_name = None

        log.instance_logger(self, echoflag=echo)
        self._creator = creator
        self._recycle = recycle
        self._invalidate_time = 0
        self._pre_ping = pre_ping
        self._reset_on_return = reset_on_return

        self.echo = echo

        if _dispatch:
            # noinspection PyUnresolvedReferences,PyProtectedMember
            self.dispatch._update(_dispatch, only_propagate=False)
        if dialect:
            self._dialect = dialect
        if events:
            for fn, target in events:
                event.listen(self, target, fn)

    async def _do_get(self):
        raise NotImplementedError()

    async def _do_return_conn(self, conn):
        raise NotImplementedError()

    async def _reset(self, conn, **kwargs):
        if self.echo:
            self.logger.debug(
                "Connection %s reset-on-return", conn,
            )
        await self._dialect.do_reset(conn, **kwargs)

    async def acquire(self):
        return await self._do_get()

    async def release(self, conn):
        await self._do_return_conn(conn)

    async def close(self):
        pass


class BaseQueuePool(AsyncPool):
    def __init__(self, creator, pool_size=5, max_overflow=10, timeout=30, **kwargs):
        super().__init__(creator, **kwargs)
        self._size = pool_size
        self._overflow = 0 - pool_size
        self._max_overflow = max_overflow
        self._timeout = timeout
        self._closed = False

    def _maybe_close_complete(self):
        if self._closed and self._overflow == 0 - self._size:
            self._close_complete()

    async def _close_conn(self, conn=None):
        try:
            if conn is not None:
                await self._dialect.disconnect(conn)
        finally:
            self._overflow -= 1
            self._maybe_close_complete()

    async def _do_get(self):
        if self._closed:
            raise InvalidRequestError("Pool is closed")

        # reached max overflow, wait on the pool
        if -1 < self._max_overflow <= self._overflow:
            rv = await self._do_get_impl()
            if rv is None:
                raise exc.TimeoutError(
                    "QueuePool limit of size %d overflow %d reached, "
                    "connection timed out, timeout %d"
                    % (self.size(), self.overflow(), self._timeout),
                    code="3o7r",
                )
            else:
                return rv

        # try to get from the pool
        rv = self._do_get_impl_no_wait()
        if rv is not None:
            return rv

        # pool is empty, create a new connection
        self._overflow += 1
        # noinspection PyBroadException
        try:
            return await self._creator()
        except BaseException:
            with util.safe_reraise():
                await self._close_conn()

    async def _do_return_conn(self, conn):
        # try to reset the connection so that it can be reused
        if not self._closed and self._reset_on_return and self.checkedin() < self._size:
            try:
                await self._reset(conn, timeout=self._timeout)
            except Exception:
                try:
                    self.logger.error(
                        "Exception during reset or similar", exc_info=True
                    )
                finally:
                    await self._close_conn(conn)
                return

        # try to put the connection back to the pool if possible, or close it
        if (
            self._closed
            or self.checkedin() >= self._size
            or not self._do_return_conn_impl(conn)
        ):
            await self._close_conn(conn)

    async def _do_get_impl(self):
        raise NotImplementedError()

    def _do_get_impl_no_wait(self):
        raise NotImplementedError()

    def _do_return_conn_impl(self, conn) -> bool:
        raise NotImplementedError()

    async def _close(self):
        raise NotImplementedError()

    def _close_complete(self):
        raise NotImplementedError()

    async def close(self):
        self._closed = True
        self._maybe_close_complete()
        await self._close()

    def size(self):
        return self._size

    def timeout(self):
        return self._timeout

    def overflow(self):
        return self._overflow

    def checkedin(self) -> int:
        raise NotImplementedError()

    def checkedout(self) -> int:
        raise NotImplementedError()


class NullPool(AsyncPool):
    async def _do_get(self):
        return await self._creator()

    async def _do_return_conn(self, conn):
        await self._dialect.disconnect(conn)


class AsyncPoolEvents(event.Events):
    _target_class_doc = "AsyncPool"
    _dispatch_target = AsyncPool

    def connect(self, dbapi_connection, connection_record):
        pass

    def first_connect(self, dbapi_connection, connection_record):
        pass
