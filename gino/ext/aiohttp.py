# noinspection PyPackageRequirements
from aiohttp.web import HTTPNotFound, middleware
from sqlalchemy.engine.url import URL

from ..api import Gino as _Gino, GinoExecutor as _Executor
from ..engine import GinoConnection as _Connection, GinoEngine as _Engine
from ..strategies import GinoStrategy


class AiohttpModelMixin:
    @classmethod
    async def get_or_404(cls, *args, **kwargs):
        # noinspection PyUnresolvedReferences
        rv = await cls.get(*args, **kwargs)
        if rv is None:
            raise HTTPNotFound(reason='{} is not found'.format(cls.__name__))
        return rv


# noinspection PyClassHasNoInit
class GinoExecutor(_Executor):
    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise HTTPNotFound(reason='No such data')
        return rv


# noinspection PyClassHasNoInit
class GinoConnection(_Connection):
    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise HTTPNotFound(reason='No such data')
        return rv


# noinspection PyClassHasNoInit
class GinoEngine(_Engine):
    connection_cls = GinoConnection

    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise HTTPNotFound(reason='No such data')
        return rv


class AiohttpStrategy(GinoStrategy):
    name = 'aiohttp'
    engine_cls = GinoEngine


AiohttpStrategy()


@middleware
class Gino(_Gino):
    """Support aiohttp.web server.

    The common usage looks like this::

        from aiohttp import web
        from gino.ext.aiohttp import Gino

        db = Gino()
        app = web.Application(middlewares=[db])
        db.init_app(app)

    By :meth:`init_app` GINO subscribes to a few signals on aiohttp, so that
    GINO could use database configuration to initialize the bound engine.

    The configuration can be passed in the ``config`` parameter of
    ``init_app``, or if that is not set, in app['config']['gino'], both of
    which should be a dictionary.

    The config includes:

    * ``driver`` - the database driver, default is ``asyncpg``.
    * ``host`` - database server host, default is ``localhost``.
    * ``port`` - database server port, default is ``5432``.
    * ``user`` - database server user, default is ``postgres``.
    * ``password`` - database server password, default is empty.
    * ``database`` - database name, default is ``postgres``.
    * ``dsn`` - a SQLAlchemy database URL to create the engine, its existence
      will replace all previous connect arguments.
    * ``pool_min_size`` - the initial number of connections of the db pool.
    * ``pool_max_size`` - the maximum number of connections in the db pool.
    * ``echo`` - enable SQLAlchemy echo mode.
    * ``ssl`` - SSL context passed to ``asyncpg.connect``, default is ``None``.
    * ``kwargs`` - other parameters passed to the specified dialects,
      like ``asyncpg``. Unrecognized parameters will cause exceptions.

    If the ``db`` is set as an aiohttp middleware, then a lazy connection is
    available at ``request['connection']``. By default, a database connection
    is borrowed on the first query, shared in the same execution context, and
    returned to the pool on response. If you need to release the connection
    early in the middle to do some long-running tasks, you can simply do this::

        await request['connection'].release(permanent=False)

    """
    model_base_classes = _Gino.model_base_classes + (AiohttpModelMixin,)
    query_executor = GinoExecutor

    def __call__(self, request, handler):
        return self._middleware(request, handler)

    async def _middleware(self, request, handler):
        async with self.acquire(lazy=True) as connection:
            request['connection'] = connection
            try:
                return await handler(request)
            finally:
                request.pop('connection', None)

    def init_app(self, app, config=None, *, db_attr_name='db'):
        app[db_attr_name] = self

        if not isinstance(config, dict):
            config = app['config'].get('gino', {})
        else:
            config = config.copy()

        async def before_server_start(_):
            if 'dsn' in config:
                dsn = config['dsn']
            else:
                dsn = URL(
                    drivername=config.setdefault('driver', 'asyncpg'),
                    host=config.setdefault('host', 'localhost'),
                    port=config.setdefault('port', 5432),
                    username=config.setdefault('user', 'postgres'),
                    password=config.setdefault('password', ''),
                    database=config.setdefault('database', 'postgres'),
                )

            await self.set_bind(
                dsn,
                echo=config.setdefault('echo', False),
                min_size=config.setdefault('pool_min_size', 5),
                max_size=config.setdefault('pool_max_size', 10),
                ssl=config.setdefault('ssl'),
                **config.setdefault('kwargs', dict()),
            )

        async def after_server_stop(_):
            await self.pop_bind().close()

        app.on_startup.append(before_server_start)
        app.on_cleanup.append(after_server_stop)

    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise HTTPNotFound(reason='No such data')
        return rv

    async def set_bind(self, bind, **kwargs):
        kwargs.setdefault('strategy', 'aiohttp')
        return await super().set_bind(bind, **kwargs)
