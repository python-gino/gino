from collections import deque

import trio

from .base import BaseQueuePool


class QueuePool(BaseQueuePool):
    def __init__(self, creator, pool_size=5, use_lifo=False, **kwargs):
        super().__init__(creator, pool_size=pool_size, **kwargs)
        self._lock = trio.Semaphore(0, max_value=pool_size)
        self._pool = deque()
        self._pool_pop = self._pool.pop if use_lifo else self._pool.popleft
        self._close_event = trio.Event()

    async def _do_get_impl(self):
        with trio.move_on_after(self._timeout):
            await self._lock.acquire()
            return self._pool_pop()

    def _do_get_impl_no_wait(self):
        try:
            self._lock.acquire_nowait()
            return self._pool_pop()
        except trio.WouldBlock:
            pass

    def _do_return_conn_impl(self, conn):
        try:
            self._lock.release()
        except ValueError:
            return False
        else:
            self._pool.append(conn)
            return True

    async def _close(self):
        with trio.move_on_after(self._timeout):
            async with trio.open_nursery() as nursery:
                while self._lock.value:
                    self._lock.acquire_nowait()
                    conn = self._pool_pop()
                    nursery.start_soon(self._close_conn, conn)
            await self._close_event.wait()

    def _close_complete(self):
        self._close_event.set()

    def checkedin(self):
        return self._lock.value

    def checkedout(self):
        return self._lock.max_value - self._lock.value + self._overflow
