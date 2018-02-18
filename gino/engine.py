from sqlalchemy.engine import Engine, Connection
from sqlalchemy import exc


class DBAPIConnection:
    def __init__(self, dialect, raw_conn):
        self._dialect = dialect
        self._raw_conn = raw_conn

    def cursor(self):
        return self._dialect.cursor_cls(self._raw_conn)


class SAConnection(Connection):
    pass


class SAEngine(Engine):
    _connection_cls = SAConnection

    def __init__(self, dialect):
        super().__init__(None, dialect, None)


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
    def __init__(self, dialect, loop):
        self._sa_engine = SAEngine(dialect)
        self._dialect = dialect
        self._loop = loop

    def acquire(self):
        return AcquireContext(self._acquire, self._release)

    async def _acquire(self):
        raw_conn = await self._dialect.acquire_conn()
        return GinoConnection(raw_conn, SAConnection(
            self._sa_engine, DBAPIConnection(self._dialect, raw_conn)))

    async def _release(self, conn):
        await self._dialect.release_conn(conn.raw_connection)

    async def close(self):
        await self._dialect.close_pool()

    async def all(self, clause, *multiparams, **params):
        async with self.acquire() as conn:
            return await conn.all(clause, *multiparams, **params)

    async def first(self, clause, *multiparams, **params):
        async with self.acquire() as conn:
            return await conn.first(clause, *multiparams, **params)

    async def scalar(self, clause, *multiparams, **params):
        async with self.acquire() as conn:
            return await conn.scalar(clause, *multiparams, **params)

    async def status(self, clause, *multiparams, **params):
        async with self.acquire() as conn:
            return await conn.status(clause, *multiparams, **params)


class GinoConnection:
    def __init__(self, raw_conn, sa_conn):
        self._raw_conn = raw_conn
        self._sa_conn = sa_conn

    @property
    def raw_connection(self):
        return self._raw_conn

    def _execute(self, clause, multiparams, params):
        if isinstance(clause, str):
            return getattr(self._sa_conn, '_execute_text')(clause, multiparams,
                                                           params)
        meth = getattr(clause, '_execute_on_connection', None)
        if meth is None:
            raise exc.ObjectNotExecutableError(clause)
        return meth(self._sa_conn, multiparams, params)

    async def all(self, clause, *multiparams, **params):
        result = self._execute(clause, multiparams, params)
        return await result.execute()

    async def first(self, clause, *multiparams, **params):
        result = self._execute(clause, multiparams, params)
        rv = await result.execute(one=True)
        if rv:
            rv = rv[0]
        return rv

    async def scalar(self, clause, *multiparams, **params):
        result = self._execute(clause, multiparams, params)
        rv = await result.execute(one=True, return_model=False)
        if rv:
            rv = rv[0][0]
        return rv

    async def status(self, clause, *multiparams, **params):
        result = self._execute(clause, multiparams, params)
        return await result.execute(status=True)
