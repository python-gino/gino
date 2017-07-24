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

    async def fetch(self, query, *args, timeout=None):
        if isinstance(query, str):
            return super().fetch(query, *args, timeout=timeout)
        model = self.metadata.guess_model(query)
        query, params = self.metadata.compile(query)
        rv = await super().fetch(query, *params, timeout=timeout)
        if model is not None:
            rv = list(map(model.from_row, rv))
        return rv

    def cursor(self, query, *args, timeout=None):
        if isinstance(query, str):
            return super().cursor(query, *args, timeout=timeout)
        model = self.metadata.guess_model(query)
        query, params = self.metadata.compile(query)
        rv = super().cursor(query, *params)
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
