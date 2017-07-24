from asyncpg.pool import Pool
from asyncpg.connection import Connection


class GinoPool(Pool):
    def __init__(self, metadata, *connect_args, min_size, max_size,
                 max_queries, max_inactive_connection_lifetime, setup, init,
                 loop, connection_class, **connect_kwargs):
        self.metadata = metadata
        super().__init__(
            *connect_args, min_size=min_size, max_size=max_size,
            max_queries=max_queries,
            max_inactive_connection_lifetime=max_inactive_connection_lifetime,
            setup=setup, init=init, loop=loop,
            connection_class=connection_class, **connect_kwargs)

    async def _async__init__(self):
        rv = await super()._async__init__()
        self.metadata.bind = self
        return rv

    async def close(self):
        self.metadata.bind = None
        self.metadata = None
        return await super().close()


class GinoConnection(Connection):
    metadata = None

    async def _execute(self, query, args, limit, timeout, return_status=False,
                       guess=True, **kwargs):
        if isinstance(query, str):
            return await super()._execute(query, args, limit, timeout,
                                          return_status)

        model = self.metadata.guess_model(query) if guess else None
        query, params = self.metadata.compile(query, *args, **kwargs)
        rv = await super()._execute(query, params, limit, timeout,
                                    return_status)
        if model is not None:
            if return_status:
                rv, status, completed = rv
            rv = list(map(model.from_row, rv))
            if return_status:
                # noinspection PyUnboundLocalVariable
                rv = rv, status, completed
        return rv

    async def fetchval(self, query, *args, column=0, timeout=None):
        self._check_open()
        data = await self._execute(query, args, 1, timeout, guess=False)
        if not data:
            return None
        return data[0][column]

    async def execute(self, query, *args, timeout: float=None,
                      **kwargs) -> str:
        if isinstance(query, str):
            return await super().execute(query, *args, timeout=timeout)

        self._check_open()
        query, params = self.metadata.compile(query, *args, **kwargs)

        if not params:
            return await self._protocol.query(query, timeout)

        _, status, _ = await super()._execute(query, args, 0, timeout, True)
        return status.decode()

    def cursor(self, query, *args, prefetch=None, timeout=None, **kwargs):
        if isinstance(query, str):
            return super().cursor(query, *args,
                                  prefetch=prefetch, timeout=timeout)

        self._check_open()
        model = self.metadata.guess_model(query)
        query, params = self.metadata.compile(query, *args, **kwargs)
        rv = super().cursor(query, *params, prefetch=prefetch, timeout=timeout)
        if model is not None:
            rv = model.map(rv)
        return rv


class AsyncpgMixin:
    def create_pool(self, dsn=None, *,
                    min_size=10,
                    max_size=10,
                    max_queries=50000,
                    max_inactive_connection_lifetime=300.0,
                    setup=None,
                    init=None,
                    loop=None,
                    connection_class=GinoConnection,
                    **connect_kwargs):
        if not issubclass(connection_class, GinoConnection):
            raise TypeError(
                'connection_class is expected to be a subclass of '
                'gino.GinoConnection, got {!r}'.format(connection_class))

        connection_class = type(connection_class.__name__, (connection_class,),
                                {'metadata': self})
        # noinspection PyAttributeOutsideInit
        pool = GinoPool(
            self, dsn,
            connection_class=connection_class,
            min_size=min_size, max_size=max_size,
            max_queries=max_queries, loop=loop, setup=setup, init=init,
            max_inactive_connection_lifetime=max_inactive_connection_lifetime,
            **connect_kwargs)
        return pool
