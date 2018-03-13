# noinspection PyPackageRequirements
from sanic.exceptions import NotFound
from sqlalchemy.engine.url import URL
try:
    # noinspection PyPackageRequirements
    from aiocontextvars import enable_inherit, disable_inherit
except ImportError:
    enable_inherit = disable_inherit = lambda: None

from ..api import Gino as _Gino, GinoExecutor as _Executor
from ..engine import GinoConnection as _Connection, GinoEngine as _Engine
from ..strategies import GinoStrategy


class SanicModelMixin:
    @classmethod
    async def get_or_404(cls, *args, **kwargs):
        # noinspection PyUnresolvedReferences
        rv = await cls.get(*args, **kwargs)
        if rv is None:
            raise NotFound('{} is not found'.format(cls.__name__))
        return rv


# noinspection PyClassHasNoInit
class GinoExecutor(_Executor):
    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise NotFound('No such data')
        return rv


# noinspection PyClassHasNoInit
class GinoConnection(_Connection):
    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise NotFound('No such data')
        return rv


# noinspection PyClassHasNoInit
class GinoEngine(_Engine):
    connection_cls = GinoConnection

    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise NotFound('No such data')
        return rv


class SanicStrategy(GinoStrategy):
    name = 'sanic'
    engine_cls = GinoEngine


SanicStrategy()


# noinspection PyClassHasNoInit
class Gino(_Gino):
    """Support Sanic web server.

    By :meth:`init_app` GINO registers a few hooks on Sanic, so that GINO could
    use database configuration in Sanic `config` to initialize the bound pool.

    A lazy connection context is enabled by default for every request. You can
    change this default behavior by setting `DB_USE_CONNECTION_FOR_REQUEST`
    config value to `False`. By default, a database connection is borrowed on
    the first query, shared in the same execution context, and returned to the
    pool on response. If you need to release the connection early in the middle
    to do some long-running tasks, you can simply do this:

        await request['connection'].release(permanent=False)

    Here `request['connection']` is a :class:`LazyConnection` object, see its
    doc string for more information.
    """
    model_base_classes = _Gino.model_base_classes + (SanicModelMixin,)
    query_executor = GinoExecutor

    def __init__(self, app=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        inherit_enabled = [False]

        if app.config.setdefault('DB_USE_CONNECTION_FOR_REQUEST', True):
            @app.middleware('request')
            async def on_request(request):
                request['connection'] = await self.acquire(lazy=True)

            @app.middleware('response')
            async def on_response(request, _):
                conn = request.pop('connection', None)
                if conn is not None:
                    await conn.release()

        @app.listener('before_server_start')
        async def before_server_start(_, loop):
            if app.config.setdefault('DB_USE_CONNECTION_FOR_REQUEST', True):
                enable_inherit(loop)
                inherit_enabled[0] = True

            await self.set_bind(
                URL(
                    drivername=app.config.setdefault('DB_DRIVER', 'asyncpg'),
                    host=app.config.setdefault('DB_HOST', 'localhost'),
                    port=app.config.setdefault('DB_PORT', 5432),
                    username=app.config.setdefault('DB_USER', 'postgres'),
                    password=app.config.setdefault('DB_PASSWORD', ''),
                    database=app.config.setdefault('DB_DATABASE', 'postgres'),
                ),
                min_size=app.config.setdefault('DB_POOL_MIN_SIZE', 5),
                max_size=app.config.setdefault('DB_POOL_MAX_SIZE', 10),
                loop=loop,
            )

        @app.listener('after_server_stop')
        async def after_server_stop(_, loop):
            await self.pop_bind().close()
            if inherit_enabled[0]:
                disable_inherit(loop)
                inherit_enabled[0] = False

    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise NotFound('No such data')
        return rv

    async def set_bind(self, bind, loop=None, **kwargs):
        kwargs.setdefault('strategy', 'sanic')
        return await super().set_bind(bind, loop=loop, **kwargs)
