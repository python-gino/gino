# noinspection PyPackageRequirements
from starlette.applications import Starlette
# noinspection PyPackageRequirements
from starlette.types import Message, Receive, Scope, Send
# noinspection PyPackageRequirements
from starlette.exceptions import HTTPException
# noinspection PyPackageRequirements
from starlette import status
from sqlalchemy.engine.url import URL

from ..api import Gino as _Gino, GinoExecutor as _Executor
from ..engine import GinoConnection as _Connection, GinoEngine as _Engine
from ..strategies import GinoStrategy


class StarletteModelMixin:
    @classmethod
    async def get_or_404(cls, *args, **kwargs):
        # noinspection PyUnresolvedReferences
        rv = await cls.get(*args, **kwargs)
        if rv is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND,
                                '{} is not found'.format(cls.__name__))
        return rv


# noinspection PyClassHasNoInit
class GinoExecutor(_Executor):
    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, 'No such data')
        return rv


# noinspection PyClassHasNoInit
class GinoConnection(_Connection):
    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, 'No such data')
        return rv


# noinspection PyClassHasNoInit
class GinoEngine(_Engine):
    connection_cls = GinoConnection

    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, 'No such data')
        return rv


class StarletteStrategy(GinoStrategy):
    name = 'starlette'
    engine_cls = GinoEngine


StarletteStrategy()


class _Middleware:
    def __init__(self, app, db):
        self.app = app
        self.db = db

    async def __call__(self, scope: Scope, receive: Receive,
                       send: Send) -> None:
        if (scope['type'] == 'http' and
                self.db.config['use_connection_for_request']):
            scope['connection'] = await self.db.acquire(lazy=True)
            await self.app(scope, receive, send)
            conn = scope.pop('connection', None)
            if conn is not None:
                await conn.release()
            return

        if scope['type'] == 'lifespan':
            async def receiver() -> Message:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await self.db.set_bind(
                        self.db.config['dsn'],
                        echo=self.db.config['echo'],
                        min_size=self.db.config['min_size'],
                        max_size=self.db.config['max_size'],
                        ssl=self.db.config['ssl'],
                        **self.db.config['kwargs'],
                    )
                elif message["type"] == "lifespan.shutdown":
                    await self.db.pop_bind().close()
                return message
            await self.app(scope, receiver, send)
            return

        await self.app(scope, receive, send)


class Gino(_Gino):
    """Support Starlette server.

    The common usage looks like this::

        from starlette.applications import Starlette
        from gino.ext.starlette import Gino

        app = Starlette()
        db = Gino(app, **kwargs)

    GINO adds a middleware to the Starlette app to setup and cleanup database
    according to the configurations that passed in the ``kwargs`` parameter.

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
    * ``use_connection_for_request`` - flag to set up lazy connection for
      requests.
    * ``kwargs`` - other parameters passed to the specified dialects,
      like ``asyncpg``. Unrecognized parameters will cause exceptions.

    If ``use_connection_for_request`` is set to be True, then a lazy connection
    is available at ``request['connection']``. By default, a database
    connection is borrowed on the first query, shared in the same execution
    context, and returned to the pool on response. If you need to release the
    connection early in the middle to do some long-running tasks, you can
    simply do this::

        await request['connection'].release(permanent=False)

    """
    model_base_classes = _Gino.model_base_classes + (StarletteModelMixin,)
    query_executor = GinoExecutor

    def __init__(self, app: Starlette, *args, **kwargs):
        self.config = dict()
        if 'dsn' in kwargs:
            self.config['dsn'] = kwargs.pop('dsn')
        else:
            self.config['dsn'] = URL(
                drivername=kwargs.pop('driver', 'asyncpg'),
                host=kwargs.pop('host', 'localhost'),
                port=kwargs.pop('port', 5432),
                username=kwargs.pop('user', 'postgres'),
                password=kwargs.pop('password', ''),
                database=kwargs.pop('database', 'postgres'),
            )
        self.config['echo'] = kwargs.pop('echo', False)
        self.config['min_size'] = kwargs.pop('pool_min_size', 5)
        self.config['max_size'] = kwargs.pop('pool_max_size', 10)
        self.config['ssl'] = kwargs.pop('ssl', None)
        self.config['use_connection_for_request'] = \
            kwargs.pop('use_connection_for_request', True)
        self.config['kwargs'] = kwargs.pop('kwargs', dict())

        super().__init__(*args, **kwargs)

        app.add_middleware(_Middleware, db=self)

    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, 'No such data')
        return rv

    async def set_bind(self, bind, loop=None, **kwargs):
        kwargs.setdefault('strategy', 'starlette')
        return await super().set_bind(bind, loop=loop, **kwargs)
