import asyncio
from asyncio import Queue, LifoQueue, QueueEmpty, QueueFull, TimeoutError, Event

from .base import BaseQueuePool


class QueuePool(BaseQueuePool):
    def __init__(self, creator, pool_size=5, use_lifo=False, **kwargs):
        super().__init__(creator, pool_size=pool_size, **kwargs)
        self._pool = (LifoQueue if use_lifo else Queue)(pool_size)
        self._close_event = None

    async def _do_get_impl(self):
        try:
            return await asyncio.wait_for(self._pool.get(), self._timeout)
        except TimeoutError:
            pass

    def _do_get_impl_no_wait(self):
        try:
            return self._pool.get_nowait()
        except QueueEmpty:
            pass

    def _do_return_conn_impl(self, conn):
        try:
            self._pool.put_nowait(conn)
        except QueueFull:
            return False
        else:
            return True

    async def _close(self):
        fs = []
        while self._pool.qsize():
            conn = self._pool.get_nowait()
            fs.append(asyncio.ensure_future(self._close_conn(conn)))
        try:
            if self._close_event is None:
                self._close_event = Event()
            await asyncio.wait_for(self._close_event.wait(), self._timeout)
        except TimeoutError:
            for fut in fs:
                fut.cancel()

    def _close_complete(self):
        if self._close_event is None:
            self._close_event = Event()
        self._close_event.set()

    def checkedin(self):
        return self._pool.qsize()

    def checkedout(self):
        return self._pool.maxsize - self._pool.qsize() + self._overflow
