import asyncio

# noinspection PyPackageRequirements
from quart import Quart, request
# noinspection PyPackageRequirements
from quart.exceptions import NotFound
from sqlalchemy.engine.url import URL

from ..api import Gino as _Gino, GinoExecutor as _Executor
from ..engine import GinoConnection as _Connection, GinoEngine as _Engine
from ..strategies import GinoStrategy


class QuartModelMixin:
    @classmethod
    async def get_or_404(cls, *args, **kwargs):
        # noinspection PyUnresolvedReferences
        rv = await cls.get(*args, **kwargs)
        if rv is None:
            raise NotFound()
        return rv


class GinoExecutor(_Executor):
    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise NotFound()
        return rv


class GinoConnection(_Connection):
    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise NotFound()
        return rv


class GinoEngine(_Engine):
    connection_cls = GinoConnection

    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise NotFound()
        return rv


class QuartStrategy(GinoStrategy):
    name = 'quart'
    engine_cls = GinoEngine


QuartStrategy()


# noinspection PyClassHasNoInit
class Gino(_Gino):
    """Support Quart web server.

    By :meth:`init_app` GINO registers a few hooks on Quart, so that GINO could
    use database configuration in Quart ``config`` to initialize the bound
    engine.

    A lazy connection context is enabled by default for every request. You can
    change this default behavior by setting ``DB_USE_CONNECTION_FOR_REQUEST``
    config value to ``False``. By default, a database connection is borrowed on
    the first query, shared in the same execution context, and returned to the
    pool on response. If you need to release the connection early in the middle
    to do some long-running tasks, you can simply do this::

        await request.connection.release(permanent=False)

    This doesn't apply to websocket, because websocket is usually a long
    connection, so it's not efficient to hold the connection.

    """
    model_base_classes = _Gino.model_base_classes + (QuartModelMixin,)
    query_executor = GinoExecutor

    def __init__(self, app=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Quart):
        if app.config.setdefault('DB_USE_CONNECTION_FOR_REQUEST', True):
            @app.before_request
            async def before_request():
                request.connection = await self.acquire(lazy=True)

            @app.after_request
            async def after_response(response):
                conn = getattr(request, 'connection', None)
                if conn is not None:
                    await conn.release()
                    del request.connection
                return response

        @app.before_first_request
        async def before_first_request():
            dsn = app.config.get('DB_DSN')
            if not dsn:
                dsn = URL(
                    drivername=app.config.setdefault('DB_DRIVER', 'asyncpg'),
                    host=app.config.setdefault('DB_HOST', 'localhost'),
                    port=app.config.setdefault('DB_PORT', 5432),
                    username=app.config.setdefault('DB_USER', 'postgres'),
                    password=app.config.setdefault('DB_PASSWORD', ''),
                    database=app.config.setdefault('DB_DATABASE', 'postgres'),
                )

            await self.set_bind(
                dsn,
                echo=app.config.setdefault('DB_ECHO', False),
                min_size=app.config.setdefault('DB_POOL_MIN_SIZE', 5),
                max_size=app.config.setdefault('DB_POOL_MAX_SIZE', 10),
                ssl=app.config.setdefault('DB_SSL'),
                loop=asyncio.get_event_loop(),
                **app.config.setdefault('DB_KWARGS', dict()),
            )

    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise NotFound()
        return rv

    async def set_bind(self, bind, loop=None, **kwargs):
        kwargs.setdefault('strategy', 'quart')
        return await super().set_bind(bind, loop=loop, **kwargs)
