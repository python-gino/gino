import asyncio


class AcquireContext:
    def __init__(self, acquire, release):
        self._acquire = acquire
        self._release = release
        self._conn = None

    async def __aenter__(self):
        self._conn = await self._acquire()
        return self._conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._release(self._conn)


class GinoEngine:
    def __init__(self, dialect, loop=None):
        self._dialect = dialect
        if loop is None:
            loop = asyncio.get_event_loop()
        self._loop = loop

    def acquire(self):
        return AcquireContext(self._acquire, self._release)

    async def _acquire(self):
        return GinoConnection(await self._dialect.acquire_conn())

    async def _release(self, conn):
        await self._dialect.release_conn(conn.raw_connection)


class GinoConnection:
    def __init__(self, raw_conn):
        self._raw_conn = raw_conn

    @property
    def raw_connection(self):
        return self._raw_conn
