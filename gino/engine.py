import asyncio


class GinoEngine:
    def __init__(self, dialect, loop=None):
        self._dialect = dialect
        if loop is None:
            loop = asyncio.get_event_loop()
        self._loop = loop
