import asyncio
import typing

import tornado
import tornado.ioloop
import tornado.iostream
import tornado.log
import tornado.platform.asyncio
import tornado.web
import tornado.gen

from tornado.options import options as _options, define as _define

from sqlalchemy.engine.url import URL

try:
    # noinspection PyPackageRequirements
    from aiocontextvars import enable_inherit as _enable_inherit
except ImportError:
    _enable_inherit = lambda: None

from ..api import Gino as _Gino, GinoExecutor as _Executor
from ..engine import GinoConnection as _Connection, GinoEngine as _Engine
from ..strategies import GinoStrategy as _GinoStrategy


__all__ = ['Gino', 'Application', 'GinoRequestHandler']


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


class TornadoStrategy(_GinoStrategy):
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

        class _Model(__CRUDModel, TornadoModelMixin, metaclass=__ModelType):
            ...

        # noinspection PyPropertyDefinition
        @property
        def Model(self) -> _Model:
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

    async def late_init(self, db: Gino, *, loop=None, options=_options,
                        additional_options=None):
        """
        Initialize this application with a database object.

        This method does a few things to setup application for working with
        the database:

        - it enables task local storage;
        - creates a connection pool and binds it to the passed database object;
        - populates :py:attr:`~.db`.

        :param db: the :py:class:`gino.ext.tornado.Gino()` class instance that
            will be used in this application.
        :param loop: io loop that will be used to run http server, either
            tornado's or asyncio's.
        :param options: a tornado's ``OptionParser()`` instance or any
            dictionary-like object with the database settings. Default is to
            use ``tornado.options.options`` global.
        :param additional_options: dict of additional options that will
            be passed directly to the :py:meth:`~.Gino.set_bind()`.

        """

        if tornado.version_info < (5, 0, 1):
            raise RuntimeError('tornado>=5.0.1 is required to run GINO')

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
            loop=asyncio_loop,
            **(additional_options or {})
        )


# noinspection PyAbstractClass
class GinoRequestHandler(tornado.web.RequestHandler):
    """
    Base class for all request handlers that use GINO.

    Manages lazy connections for each request.

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

    async def _setup_connection(self):
        """
        Hook for creating connection.

        """
        # Ensure that we have a current task assigned. Otherwise,
        # lazy connections may not work properly.
        assert asyncio.Task.current_task() is not None

        if self.use_connection_for_request:
            self.__db_connection = await self.db.acquire(lazy=True)

    async def _teardown_connection(self):
        """
        Hook for destroying connection.

        """

        if self.__db_connection is not None:
            await self.__db_connection.release()
            self.__db_connection = None

    # noinspection PyBroadException
    @tornado.gen.coroutine
    def _execute(self, *args, **kwargs):
        try:
            try:
                yield self._setup_connection()
                yield from super(GinoRequestHandler, self)._execute(*args, **kwargs)
            finally:
                yield self._teardown_connection()
        except Exception as e:
            tornado.log.app_log.exception('exception during lazy connection '
                                          'setup/teardown')
            try:
                self._handle_request_exception(e)
            except Exception:
                tornado.log.app_log.exception('exception in exception handler')
            if self._prepared_future is not None:
                if not self._prepared_future.done():
                    self._prepared_future.set_result(None)
