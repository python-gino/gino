"""
GINO provides a convenient plugin for integrating with Tornado_ webserver.
It consists of two parts, each of them is optional.

.. _Tornado: http://www.tornadoweb.org

.. warning::

    Tornado doesn't wrap request handlers to asyncio tasks, hence
    task locals doesn't work in request handlers by default. To fix this,
    you may either redefine ``_execute()`` method on you handlers to wrap
    request processing into a task, or simply use
    :py:class:`gino.ext.tornado.AsyncioRequestHandler`
    as a base class for all of your handlers.

    See `integrate GINO with application and request handlers`_ for more details.


Provide tornado-specific methods on models
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

GINO can provide a webframework-aware ``.get_or_404()`` method which work
similar to ``.get()`` but raises an appropriate error whenever requested object
not found. In case of tornado, an appropriate error is
``tornado.web.HTTPError(404)``.

To have it working, simply use :py:class:`gino.ext.tornado.Gino` as your
database metadata.


Integrate GINO with application and request handlers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In addition to ``.get_or_404()``, GINO provides bases for application and
request handler objects.

Inherit your application class from :py:class:`gino.ext.tornado.Application`
to automate connection pool management and provide access to the database
object to all of your request handlers via ``self.application.db``.

Inherit your request handlers from
:py:class:`gino.ext.tornado.AsyncioRequestHandler` to enable task locals
support.

Inherit your request handlers from :py:class:`gino.ext.tornado.GinoRequestHandler`
to enable active connection management.
Note that :py:class:`gino.ext.tornado.GinoRequestHandler` requires your application
to have a ``db`` property with ``acquire`` coroutine so its best to use it
with :py:class:`gino.ext.tornado.Application`.


Settings defined by this extension
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

GINO would define some options for database configuration. Use them with
the standard ``tornado.options`` module:

- ``'db_driver'`` -- if not set, ``asyncpg``;
- ``'db_host'`` -- if not set, ``localhost``;
- ``'db_port'`` -- if not set, ``5432``;
- ``'db_user'`` -- if not set, ``postgres``;
- ``'db_password'`` -- if not set, empty string;
- ``'db_database'`` -- if not set, ``postgres``;
- ``'db_pool_min_size'`` -- number of connection the pool will be initialized
  with. Default is ``5``;
- ``'db_pool_max_size'`` -- max number of connections in the pool.
  Default is ``10``;
- ``'db_pool_max_inactive_conn_lifetime'`` -- number of seconds after which
  inactive connections in the pool will be closed.  Pass ``0`` to disable this
  mechanism. Default is ``300``;
- ``'db_pool_max_queries '`` -- number of queries after a connection is closed
  and replaced with a new connection. Default is ``50000``.


An example application
^^^^^^^^^^^^^^^^^^^^^^

A helloworld application that uses tornado and GINO may look like this:

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
            user: User = await User.get_or_404(int(uid))
            self.write(f'Hi, {user.nickname}!')


    if __name__ == '__main__':
        tornado.options.parse_command_line()
        tornado.ioloop.IOLoop.configure('tornado.platform.asyncio.AsyncIOMainLoop')

        app = Application([
            tornado.web.URLSpec(r'/', AllUsers, name='index'),
            tornado.web.URLSpec(r'/user/(?P<uid>[0-9]+)', GetUser, name='user')
        ], debug=True)

        loop = tornado.ioloop.IOLoop.current().asyncio_loop

        # If you intend to use HTTPServer in multiprocessed environment,
        # call the app.late_init method after calling HTTPServer.start(n).
        # This will create one connection pool per process.
        loop.run_until_complete(app.late_init(db))

        app.listen(8888)

        loop.run_forever()

API reference
^^^^^^^^^^^^^

"""

import asyncio
import sys
import typing

import tornado.ioloop
import tornado.iostream
import tornado.log
import tornado.platform.asyncio
import tornado.web

from sqlalchemy.engine.url import URL
from tornado.options import options as _options, define as _define
try:
    # noinspection PyPackageRequirements
    from aiocontextvars import enable_inherit as _enable_inherit
except ImportError:
    _enable_inherit = lambda: None

from ..api import Gino as _Gino, GinoExecutor as _Executor
from ..engine import GinoConnection as _Connection, GinoEngine as _Engine
from ..strategies import GinoStrategy


def _assert_not_negative(name):
    def inner(value):
        if value < 0:
            raise ValueError(f'{name} should be non-negative')
    return inner


_define('db_driver', 'asyncpg', str, group='database')
_define('db_host', 'localhost', str, group='database')
_define('db_port', 5432, int, group='database')
_define('db_user', 'postgres', str, group='database')
_define('db_password', 'password', str, group='database')
_define('db_database', 'postgres', str, group='database')
_define('db_pool_min_size', 5, int, group='database',
        callback=_assert_not_negative('db_pool_min_size'))
_define('db_pool_max_size', 10, int, group='database',
        callback=_assert_not_negative('db_pool_max_size'))
_define('db_pool_max_inactive_conn_lifetime', 300, float, group='database',
        callback=_assert_not_negative('db_pool_max_inactive_conn_lifetime'))
_define('db_pool_max_queries', 50000, int, group='database',
        callback=_assert_not_negative('db_pool_max_queries'))


class TornadoModelMixin:
    @classmethod
    async def get_or_404(cls, *args, **kwargs):
        # noinspection PyUnresolvedReferences
        rv = await cls.get(*args, **kwargs)
        if rv is None:
            raise tornado.web.HTTPError(404)
        return rv


# noinspection PyClassHasNoInit
class GinoExecutor(_Executor):
    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise tornado.web.HTTPError(404)
        return rv


# noinspection PyClassHasNoInit
class GinoConnection(_Connection):
    async def first_or_404(self, *args, **kwargs):
        rv = await self.first(*args, **kwargs)
        if rv is None:
            raise tornado.web.HTTPError(404)
        return rv


# noinspection PyClassHasNoInit
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


class Application(tornado.web.Application):
    """
    Base application that provides access to the database object and defines
    a convenient method for initializing all the database-related stuff.

    """

    #: The database object associated with this application.
    #: Use :py:meth:`~.late_init()` to init this or set it manually.
    db: Gino = None

    #: If ``True``, enables ``GinoRequestHandler`` to create lazy connections.
    #:
    #: See :py:attr:`~.GinoRequestHandler.use_connection_for_request`
    #: for more info.
    use_connection_for_request: bool = True

    async def late_init(self, db: Gino, *, loop=None, options=_options):
        """
        Initialize this application with a database object.

        This method does a few things to setup application for working with
        the database:

        - it enables task local storage;
        - creates a connection pool and binds it to the passed database object;
        - populates :py:attr:`~.db`.

        :param db: the :py:class:`gino.ext.tornado.Gino()` class instance that
            will be used in this application.
        :param loop: io loop that will be used to run heep server, either
            tornado's or asyncio's.
        :param options: a tornado's ``OptionParser()`` instance or any
            dictionary-like object with the database settings. Default is to
            use ``tornado.options.options`` global.

        """

        if loop is None:
            loop = tornado.ioloop.IOLoop.current()
        if isinstance(loop, tornado.platform.asyncio.BaseAsyncIOLoop):
            asyncio_loop = loop.asyncio_loop
        elif isinstance(loop, asyncio.BaseEventLoop):
            asyncio_loop = loop
        else:
            raise RuntimeError('AsyncIOLoop is required to run GINO')

        _enable_inherit(asyncio_loop)

        self.db: Gino = db
        await db.set_bind(
            URL(
                drivername=options['db_driver'],
                host=options['db_host'],
                port=options['db_port'],
                username=options['db_user'],
                password=options['db_password'],
                database=options['db_database'],
            ),
            min_size=options['db_pool_min_size'],
            max_size=options['db_pool_max_size'],
            max_inactive_connection_lifetime=(
                options['db_pool_max_inactive_conn_lifetime']
            ),
            max_queries=options['db_pool_max_queries'],
            loop=asyncio_loop
        )


# noinspection PyAbstractClass
class AsyncioRequestHandler(tornado.web.RequestHandler):
    """
    This class enables support for task locals by wrapping the ``_execute()``
    method into ``asyncio.Task`` instances.

    """

    application: tornado.web.Application

    async def _setup_connection(self):
        """
        Hook for creating connection.

        """
        pass

    async def _teardown_connection(self):
        """
        Hook for destroying connection.

        """
        pass

    def _execute(self, transforms, *args, **kwargs):
        loop = tornado.ioloop.IOLoop.current()

        if not isinstance(loop, tornado.platform.asyncio.BaseAsyncIOLoop):
            raise RuntimeError('AsyncIOLoop is required to run GINO')

        asyncio_loop = loop.asyncio_loop

        return asyncio.ensure_future(
            self._do_execute(transforms, *args, **kwargs),
            loop=asyncio_loop
        )

    async def _do_execute(self, transforms, *args, **kwargs):
        """
        An actual asyncio-compatible implementation on the ``_execute``.

        This function just takes the original generator ``_execute.__wrapped__``
        and manages to pass its futures to the underlying asyncio loop.

        It also calls ``_setup_connection`` and ``_teardown_connection``
        methods and manages all errors that happen there.

        """

        self._transforms = transforms

        try:
            gen = super()._execute.__wrapped__(
                self, transforms, *args, **kwargs
            )

            data = None
            exc_info = None

            await self._setup_connection()

            try:
                while True:
                    try:
                        if exc_info is None:
                            coro = gen.send(data)
                        else:
                            coro = gen.throw(*exc_info)
                    except StopIteration:
                        return
                    exc_info = None
                    data = None
                    # noinspection PyBroadException
                    try:
                        data = await coro
                    except:
                        exc_info = sys.exc_info()
            finally:
                await self._teardown_connection()
        except Exception as e:
            # noinspection PyBroadException
            try:
                self._handle_request_exception(e)
            except Exception:
                tornado.log.app_log.exception("exception in exception handler")
        finally:
            if self._prepared_future is not None:
                if not self._prepared_future.done():
                    self._prepared_future.set_result(None)


# noinspection PyAbstractClass
class GinoRequestHandler(AsyncioRequestHandler):
    """
    Base class for all request handlers that use GINO.

    In addition to features provided by :py:class:`~.AsyncioRequestHandler`,
    this class manages lazy connections for each request.

    """

    application: Application

    __db_connection = None

    @property
    def use_connection_for_request(self):
        """
        If ``True``, a lazy connection is created for each request.

        That is, whenever the first query occurs, a new connection is
        borrowed from the application's db object. All succeeding queries made
        within this request will reuse that connection. The connection will be
        returned to the pool once the request is finished or the
        :py:meth:`~.release_connection()` method is called explicitly.

        This property is equal to
        :py:attr:`Application.use_connection_for_request`
        by default.

        """
        return self.application.use_connection_for_request

    @property
    def db(self):
        """
        Access to the database object.

        This property is equal to :py:attr:`Application.db` by default.

        """
        return self.application.db

    async def _setup_connection(self):
        if self.use_connection_for_request:
            self.__db_connection = await self.db.acquire(lazy=True)

    async def _teardown_connection(self):
        if self.__db_connection is not None:
            await self.__db_connection.release()
            self.__db_connection = None

    @property
    def db_connection(self):
        """
        The actual connection associated with this request or ``None`` if
        ``use_connection_for_request`` is ``False``.

        """
        return self.__db_connection

    async def release_connection(self):
        """
        Return the connection associated with this request back to the pool.

        """
        await self._teardown_connection()
