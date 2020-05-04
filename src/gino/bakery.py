import copy
import inspect

from sqlalchemy import text

from .api import GinoExecutor, _PlaceHolder
from .exceptions import UninitializedError, InitializedError


class BakedQuery(GinoExecutor):
    """Represents a pre-compiled and possibly prepared query for faster execution.

    :class:`BakedQuery` is created by :meth:`Bakery.bake`, and can be executed by
    :class:`~gino.engine.GinoEngine` or :class:`~gino.engine.GinoConnection`. If there
    is a proper bind in the baked query, contextual execution APIs inherited from
    :class:`~.api.GinoExecutor` can also be used.

    .. versionadded:: 1.1
    """

    def __init__(self, elem, metadata, hash_=None):
        super().__init__(self)
        self._elem = elem
        self._metadata = metadata
        if hash_ is None:
            self._hash = hash(elem)
        else:
            self._hash = hash_
        self._compiled_sql = None
        self._sql = None

    def _set_sql(self, sql):
        self._sql = sql

    def _execute_on_connection(self, conn, multiparams, params):
        return conn._execute_baked_query(self, multiparams, params)

    def get(self, _):
        """Internal API to get the :attr:`compiled_sql`.

        :param _: Ignored.
        """
        return self.compiled_sql

    def __setitem__(self, key, value):
        self._compiled_sql = value

    @property
    def compiled_sql(self):
        """Internal API to get the SQLAlchemy compiled sql context."""
        return self._compiled_sql

    @property
    def sql(self):
        """Internal API to get the compiled raw SQL."""
        return self._sql

    @property
    def query(self):
        """Internal API to get the query instance before compilation."""
        return self._elem

    @property
    def bind(self):
        """Internal API to provide a proper bind if found."""
        rv = self._elem.bind
        if rv is not None:
            return rv
        if self._metadata is None:
            return _PlaceHolder(UninitializedError("Gino engine is not initialized."))
        return self._metadata.bind

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        return self._hash == getattr(other, "_hash", None)

    def execution_options(self, **kwargs):
        """
        Set execution options on a shadow query of this baked query.

        The execution options set in this method won't affect the execution options in
        the baked query.

        Read :meth:`~gino.engine.GinoConnection.execution_options` for more
        information.

        :param options: Multiple execution options.
        :return: A shadow of the baked query with new execution options but still
                 functions as a baked query.
        """
        rv = _ShadowBakedQuery(self)
        return rv.execution_options(**kwargs)


class _ShadowBakedQuery(BakedQuery):
    def __init__(self, bq):
        super().__init__(bq.query, bq._metadata, hash(bq))
        self._compiled_sql = copy.copy(bq.compiled_sql)
        self._sql = bq._sql

    def execution_options(self, **kwargs):
        self._elem = self._elem.execution_options(**kwargs)
        self._compiled_sql.execution_options = self._elem.get_execution_options()
        return self


class Bakery:
    """Factory and warehouse of baked queries.

    You may provide a bakery to a :class:`~gino.engine.GinoEngine` during creation as
    the ``bakery`` keyword argument, and the engine will bake the queries and create
    corresponding prepared statements for each of the connections in the pool.

    A :class:`~gino.api.Gino` instance has a built-in :attr:`~gino.api.Gino.bakery`,
    it's automatically given to the engine during :meth:`~gino.api.Gino.set_bind` or
    :meth:`~gino.api.Gino.with_bind`.

    .. versionadded:: 1.1
    """

    query_cls = BakedQuery

    def __init__(self):
        self._queries = []
        self._closed = False

    def __iter__(self):
        return iter(self._queries)

    def bake(self, func_or_elem=None, **execution_options):
        """Bake a query.

        You can bake raw SQL strings or SQLAlchemy Core query instances. This method
        adds the given query into a queue in the bakery, and bakes it only when the
        bakery is set to an :class:`~gino.engine.GinoEngine` from which the bakery could
        learn about the SQL dialect and compile the queries into SQL. Once done, the
        bakery is "closed", you can neither give it to another engine, nor use it to
        bake more queries.

        :param func_or_elem: A :class:`str` or a SQLAlchemy Core query instance, or a
                             function that returns such results.
        :param execution_options: Shortcut to add SQLAlchemy execution options to the
                                  query.
        :return: A :class:`BakedQuery` instance.
        """
        if self._closed:
            raise InitializedError(
                "The bakery is closed. Please bake before feeding this bakery to a "
                "engine constructor."
            )

        if func_or_elem is None:

            def _wrapper(val):
                return self.bake(val, **execution_options)

            return _wrapper

        if callable(func_or_elem):
            if inspect.signature(func_or_elem).parameters:
                # bake decorator on model level, make it a declared_attr

                def _wrapper(cls):
                    return self.bake(func_or_elem(cls), **execution_options)

                _wrapper.__declared_attr_with_table__ = True

                return _wrapper
            else:
                elem = func_or_elem()
        else:
            elem = func_or_elem

        metadata = execution_options.pop("metadata", None)
        if isinstance(elem, str):
            elem = text(elem)
        if execution_options:
            elem = elem.execution_options(**execution_options)
        bq = self.query_cls(elem, metadata)
        self._queries.append(bq)
        return bq
