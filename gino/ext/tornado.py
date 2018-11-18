"""
GINO provides a convenient plugin for integrating with Tornado_ webserver.
It consists of two parts, each of them is optional.

.. _Tornado: http://www.tornadoweb.org


Provide tornado-specific methods on models
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

GINO can provide a web framework-aware ``.get_or_404()`` method which work
similar to ``.get()`` but raises an appropriate error whenever requested object
not found. In case of tornado, an appropriate error is
``tornado.web.HTTPError(404)``.

To have it working, simply use :py:class:`gino.ext.tornado.Gino` as your
database metadata.


Integrate GINO with application
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Initialize by ``db.init_app(app)``, and get the ``Gino`` instance in the
``RequestHandler`` by ``self.application.db``.


An example application
^^^^^^^^^^^^^^^^^^^^^^

A hello world application that uses tornado and GINO may look like this:

.. code-block:: python

    import tornado.web
    import tornado.ioloop
    import tornado.options
    import tornado.escape

    from gino.ext.tornado import Gino, Application, GinoRequestHandler


    # Define your database metadata
    # -----------------------------

    db = Gino()


    # Define tables as you would normally do
    # --------------------------------------

    class User(db.Model):
        __tablename__ = 'users'

        id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
        nickname = db.Column(db.Unicode(), nullable=False)


    # Now just use your tables
    # ------------------------

    class AllUsers(GinoRequestHandler):
        async def get(self):
            users = await User.query.gino.all()

            for user in users:
                url = self.application.reverse_url('user', user.id)
                nickname = tornado.escape.xhtml_escape(user.nickname)
                self.write(f'<a href="{url}">{nickname}</a><br/>')


    class GetUser(GinoRequestHandler):
        async def get(self, uid):
            async with self.application.db.acquire() as conn:
                async with conn.transaction():
                    user: User = await User.get_or_404(int(uid))
                    self.write(f'Hi, {user.nickname}!')


    if __name__ == '__main__':
        app = tornado.web.Application([
            tornado.web.URLSpec(r'/', AllUsers, name='index'),
            tornado.web.URLSpec(r'/users/(?P<uid>[0-9]+)', GetUser,
                                name='user')
        ], debug=True)
        ssl_ctx = ssl.SSLContext()
        ssl_ctx.verify_mode = ssl.CERT_NONE
        ssl_ctx.check_hostname = False
        db.init_app(app, ssl=ssl_ctx)

        app.listen(8888)
        tornado.ioloop.IOLoop.current().start()

API reference
^^^^^^^^^^^^^

"""

import asyncio
import typing

import tornado.ioloop
import tornado.iostream
import tornado.log
import tornado.platform.asyncio
import tornado.web

from sqlalchemy.engine.url import URL

from ..api import Gino as _Gino, GinoExecutor as _Executor
from ..engine import GinoConnection as _Connection, GinoEngine as _Engine
from ..strategies import GinoStrategy


class TornadoModelMixin:
    @classmethod
    async def get_or_404(cls, *args, **kwargs):
        # noinspection PyUnresolvedReferences
        rv = await cls.get(*args, **kwargs)
        if rv is None:
            raise tornado.web.HTTPError(404)
        return rv


class GinoExecutor(_Executor):
    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise tornado.web.HTTPError(404)
        return rv


class GinoConnection(_Connection):
    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise tornado.web.HTTPError(404)
        return rv


class GinoEngine(_Engine):
    connection_cls = GinoConnection

    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise tornado.web.HTTPError(404)
        return rv


class TornadoStrategy(GinoStrategy):
    name = 'tornado'
    engine_cls = GinoEngine


TornadoStrategy()


class Gino(_Gino):
    """
    Base class for GINO database.

    Using this class as a metadata for your database adds an additional
    ``get_or_404()`` method to all of your table classes.

    """

    model_base_classes = _Gino.model_base_classes + (TornadoModelMixin,)
    query_executor = GinoExecutor

    if typing.TYPE_CHECKING:
        # Typehints to enable autocompletion on all Gino.Model-derived classes

        from ..crud import CRUDModel as __CRUDModel
        from ..declarative import ModelType as __ModelType

        class Model(__CRUDModel, TornadoModelMixin, metaclass=__ModelType):
            ...

    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise tornado.web.HTTPError(404)
        return rv

    async def set_bind(self, bind, loop=None, **kwargs):
        kwargs.setdefault('strategy', 'tornado')
        return await super().set_bind(bind, loop=loop, **kwargs)

    def init_app(self, app, *, loop=None, dsn='', driver='asyncpg',
                 host='localhost', port=5432,
                 user='postgres', password='', database='postgres',
                 echo=False, pool_min_size=5, pool_max_size=10, ssl=None):
        """
        Initialize database

        :param loop: User-defined event loop. If not defined, tornado default
        loop will be used.
        :param driver: the database driver, default is ``asyncpg``.
        :param host: database server host, default is ``localhost``.
        :param port: database server port, default is ``5432``.
        :param user: database server user, default is ``postgres``.
        :param password: database server password, default is empty.
        :param database: database name, default is ``postgres``.
        :param dsn: a SQLAlchemy database URL to create the engine, its
        existence will replace all previous connect arguments.
        :param echo: enable SQLAlchemy echo mode.
        :param pool_min_size: the initial number of connections of the db
        pool, default is ``5``.
        :param pool_max_size: the maximum number of connections in the db
        pool, default is ``10``.
        :param ssl: SSL context passed to ``asyncpg.connect``, default is
        ``None``. This can be ``True`` or an instance of ``ssl.SSLContext``.
        """
        if loop is None:
            loop = tornado.ioloop.IOLoop.current()
        if isinstance(loop, tornado.platform.asyncio.BaseAsyncIOLoop):
            asyncio_loop = loop.asyncio_loop
        elif isinstance(loop, asyncio.BaseEventLoop):
            asyncio_loop = loop
        else:
            raise RuntimeError('AsyncIOLoop is required to run GINO')

        if not dsn:
            dsn = URL(
                drivername=driver, host=host, port=port, username=user,
                password=password, database=database,
            )

        async def set_bind():
            await self.set_bind(
                dsn, echo=echo, min_size=pool_min_size, max_size=pool_max_size,
                ssl=ssl, loop=asyncio_loop,
            )

        asyncio_loop.run_until_complete(set_bind())
        app.db = self
