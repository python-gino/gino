import asyncio
import functools


class Deferred:
    __slots__ = ('_awaitable', '_fut')

    def __init__(self, awaitable):
        self._awaitable = awaitable
        self._fut = None

    async def _run(self):
        if self._fut is None:
            self._fut = asyncio.Future()
            try:
                self._fut.set_result(await self._awaitable)
            except Exception as e:
                self._fut.set_exception(e)
        return await self._fut

    def __await__(self):
        return self._run().__await__()


def deferred(method):
    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        return Deferred(method(*args, **kwargs))
    return wrapper
