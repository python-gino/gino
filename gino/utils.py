import asyncio


class Deferred:
    __slots__ = ('_awaitable', '_loop')

    def __init__(self, awaitable, *, loop=None):
        self._awaitable = awaitable
        self._loop = loop

    async def _get(self):
        if not asyncio.isfuture(self._awaitable):
            loop = self._loop or asyncio.get_event_loop()
            coro, self._awaitable = self._awaitable, loop.create_future()
            try:
                result = await coro
            except BaseException as e:
                self._awaitable.set_exception(e)
                raise
            else:
                self._awaitable.set_result(result)
                return result
        return await self._awaitable

    @property
    def done(self):
        return asyncio.isfuture(self._awaitable) and self._awaitable.done()

    @property
    def result(self):
        return self._awaitable.result()

    def __await__(self):
        return self._get().__await__()

    def __getattr__(self, item):
        if self.done:
            return getattr(self.result, item)
        else:
            raise ValueError('Deferred object not awaited')
