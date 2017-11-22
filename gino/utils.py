class Deferred:
    __slots__ = ('_awaitable', '_success', '_result')

    def __init__(self, awaitable):
        self._awaitable = awaitable
        self._success = True
        self._result = None

    async def _get(self):
        if self._awaitable is not None:
            awaitable, self._awaitable = self._awaitable, None
            try:
                self._result = await awaitable
                self._success = True
                return self._result
            except BaseException as e:
                self._result = e
                self._success = False
                raise
        if self._success:
            return self._result
        else:
            raise self._result

    def __await__(self):
        return self._get().__await__()
