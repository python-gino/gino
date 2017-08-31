"""
Integrate GINO and Tornado webserver
====================================

We provide a convenient way to integrate GINO and tornado.

A few steps required to get it working:

- use the :py:class:`gino.ext.tornado.Gino` class as your database metadata;
- derive your app class from :py:class:`gino.ext.tornado.Application` or use
  the ``Application`` directly;
- derive your request handlers from
  :py:class:`gino.ext.tornado.RequestHandlerBase`.
- run :py:meth:`.Application.late_init` coroutine somewhere between spawning
  an ``HTTPServer`` and starting the main loop.

That's it! We will automatically create a connection pool for you, assign
a connection to request whenever you need it.

.. warning::

    Task locals as implemented by :py:module:`gino.local` utilize
    ``asyncio.Task.current_task()`` method for identifying current context.
    Naturally, it only works in coroutines that are wrapped to
    ``asyncio.Task`` class. This is not the case for default tornado
    request handlers.

    If you want to use task locals, it is critical that you inherit your
    request handlers from :py:class:`~.RequestHandlerBase`.

GINO would define some options for database configuration. Use them with
the standard ``tornado.options`` module:

- ``'db_host'`` -- if not set, ``localhost``
- ``'db_port'`` -- if not set, ``5432``
- ``'db_user'`` -- if not set, ``postgres``
- ``'db_password'`` -- if not set, empty string.
- ``'db_database'`` -- if not set, ``postgres``
- ``'db_pool_min_size'`` -- number of connection the pool will be initialized
  with. Default is ``5``
- ``'db_pool_max_size'`` -- max number of connections in the pool.
  Default is ``10``
- ``'db_pool_max_inactive_conn_lifetime'`` -- number of seconds after which
  inactive connections in the pool will be closed.  Pass ``0`` to disable this
  mechanism. Default is ``300``.
- ``'db_pool_max_queries '`` -- number of queries after a connection is closed
  and replaced with a new connection. Default is ``50000``

A helloworld application that uses tornado and GINO may look like this::

    import tornado.web
    import tornado.ioloop
    import tornado.options
    import tornado.escape

    from gino.ext.tornado import Gino, Application, RequestHandlerBase


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

    class AllUsers(RequestHandlerBase):
        async def get(self):
            users = await User.query.gino.all()

            for user in users:
                url = self.application.reverse_url('user', user.id)
                nickname = tornado.escape.xhtml_escape(user.nickname)
                self.write(f'<a href="{url}">{nickname}</a><br/>')


    class GetUser(RequestHandlerBase):
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

        loop.run_until_complete(app.late_init(db))

        app.listen(8888)

        loop.run_forever()


"""

import asyncio
import sys
import typing

import tornado.ioloop
import tornado.iostream
import tornado.log
import tornado.platform.asyncio
import tornado.web

from tornado.options import options as _options, define as _define

from ..api import Gino as _Gino, GinoPool as _GinoPool
from ..local import enable_task_local as _enable_task_local


def _assert_not_negative(name):
    def inner(value):
        if value < 0:
            raise ValueError(f'{name} should be non-negative')
    return inner


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


class Gino(_Gino):
    """
    Base class for GINO database.

    Using this class as a metadata for your database adds an additional
    ``get_or_404()`` method to all of your table classes. This method works as
    the ``get()`` method except that it would throw throw the
    ``tornado.web.HTTPError(404)`` if the requested object cannot be found.

    """

    default_model_classes = _Gino.default_model_classes + (TornadoModelMixin,)

    if typing.TYPE_CHECKING:
        # Typehints to enable autocompletion on all Gino.Model-derived classes

        from ..crud import CRUDModel as __CRUDModel
        from ..declarative import ModelType as __ModelType

        class Model(__CRUDModel, TornadoModelMixin, metaclass=__ModelType):
            ...


class Application(tornado.web.Application):
    """
    Base application that provides access to the database object and defines
    a convenient method for initializing all the database-related stuff.

    """

    #: The database object associated with this application.
    #: Use :py:meth:`~.late_init()` to init this or set it manually.
    db: Gino = None

    #: Connection pool or any pool-like bind with ``acquire()`` and
    #: ``release()`` coroutines. You may try setting this to a single
    #: connection, just remember to set ``use_connection_for_request = False``.
    db_pool: _GinoPool = None

    #: If ``True``, a lazy connection is created for each request.
    #:
    #: See :py:attr:`~.RequestHandlerBase.use_connection_for_request`
    #: for more info.
    use_connection_for_request: bool = True

    async def late_init(self, db: Gino, *, loop=None, options=_options):
        """
        Initialize this application with a database object.

        This method does a few things to setup application for working with
        the database:

        - it enables task local storage;
        - creates a connection pool and binds it to the database object;
        - populates :py:attr:`~.db` and :py:attr:`~.db_pool` attributes.

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

        _enable_task_local(asyncio_loop)

        self.db: Gino = db
        self.db_pool: _GinoPool = await db.create_pool(
            host=options['db_host'],
            port=options['db_port'],
            user=options['db_user'],
            password=options['db_password'],
            database=options['db_database'],
            min_size=options['db_pool_min_size'],
            max_size=options['db_pool_max_size'],
            max_inactive_connection_lifetime=(
                options['db_pool_max_inactive_conn_lifetime']
            ),
            max_queries=options['db_pool_max_queries'],
            loop=asyncio_loop
        )


# noinspection PyAbstractClass
class RequestHandlerBase(tornado.web.RequestHandler):
    """
    Base class for all request handlers that use GINO.

    This base class serves two main purposes. The first is to enable task
    locals by wrapping ``tornado.web.RequestHandler._execute()`` into the
    ``asyncio.Task``. The second is to acquire a lazy connection before
    request processing starts (before the ``prepare()`` method is called) and
    dispose it after it finishes (after the ``on_finish()`` method is called).

    """

    application: Application

    __db_connection = None

    @property
    def use_connection_for_request(self):
        """
        If ``True``, a lazy connection is created for each request.

        That is, whenever the first query occurs, a new connection is
        borrowed from the application's pool. All succeeding queries will
        reuse that connection. The connection will be returned to the pool
        once the request is finished or the :py:meth:`~.release_connection()`
        method is called explicitly.

        This property is equal to
        :py:attr:`~.Application.use_connection_for_request`
        by default.

        """
        return self.application.use_connection_for_request

    @property
    def db_connection(self):
        """
        The actual connection created via ``use_connection_for_request``.

        This will be ``None`` if no connection was acquired of the connection
        was returned to the pool.

        """
        return self.__db_connection

    async def release_connection(self):
        """
        Release the connection acquired via ``use_connection_for_request``.
        """
        if self.__db_connection is not None:
            await self.application.db_pool.release(self.__db_connection)
            self.__db_connection = None

    async def _setup_connection(self):
        """
        Hook for creating connection.
        """
        self.__db_connection = await self.application.db_pool.acquire(lazy=True)

    async def _teardown_connection(self):
        """
        Hook for destroying connection.
        """
        await self.release_connection()

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
        try:
            gen = super()._execute.__wrapped__(
                self, transforms, *args, **kwargs
            )

            data = None
            exc_info = None

            use_connection_for_request = self.use_connection_for_request

            if use_connection_for_request:
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
                if use_connection_for_request:
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
