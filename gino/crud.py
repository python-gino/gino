import itertools
import weakref

import sqlalchemy as sa
from sqlalchemy.sql import ClauseElement

from . import json_support
from .declarative import Model
from .exceptions import NoSuchRowError

DEFAULT = object()


class _Query:
    def __get__(self, instance, owner):
        q = sa.select([owner.__table__])
        if instance is not None:
            q = instance.append_where_primary_key(q)
        return q.execution_options(model=weakref.ref(owner))


class _Select:
    def __get__(self, instance, owner):
        def select(*args):
            q = sa.select([getattr(owner, x) for x in args])
            if instance is not None:
                q = instance.append_where_primary_key(q)
            return q.execution_options(model=weakref.ref(owner),
                                       return_model=False)
        return select


class _Update:
    def __get__(self, instance, owner):
        if instance is None:
            q = owner.__table__.update()
            return q.execution_options(model=weakref.ref(owner))
        else:
            # noinspection PyProtectedMember
            return instance._update


class _Delete:
    def __get__(self, instance, owner):
        if instance is None:
            q = owner.__table__.delete()
            return q.execution_options(model=weakref.ref(owner))
        else:
            # noinspection PyProtectedMember
            return instance._delete


class UpdateRequest:
    """
    A collection of attributes and their new values to update on one model
    instance.

    :class:`.UpdateRequest` instances are created by :attr:`.CRUDModel.update`,
    don't instantiate manually unless required. Every :class:`.UpdateRequest`
    instance is bound to one model instance, all updates are for that one
    specific model instance and its database row.

    """
    def __init__(self, instance):
        self._instance = instance
        self._values = {}
        self._props = {}
        self._literal = True
        self._clause = self._instance.append_where_primary_key(
            type(self._instance).update)

    def _set(self, key, value):
        self._values[key] = value

    def _set_prop(self, prop, value):
        if isinstance(value, ClauseElement):
            self._literal = False
        self._props[prop] = value

    async def apply(self, bind=None, timeout=DEFAULT):
        """
        Apply pending updates into database by executing an ``UPDATE`` SQL.

        :param bind: A :class:`~gino.engine.GinoEngine` to execute the SQL, or
          ``None`` (default) to use the bound engine in the metadata.

        :param timeout: Seconds to wait for the database to finish executing,
          ``None`` for wait forever. By default it will use the ``timeout``
          execution option value if unspecified.

        :return: ``self`` for chaining calls.

        """
        cls = type(self._instance)
        values = self._values.copy()

        # handle JSON columns
        json_updates = {}
        for prop, value in self._props.items():
            value = prop.save(self._instance, value)
            updates = json_updates.setdefault(prop.column_name, {})
            if self._literal:
                updates[prop.name] = value
            else:
                if isinstance(value, int):
                    value = sa.cast(value, sa.BigInteger)
                elif not isinstance(value, ClauseElement):
                    value = sa.cast(value, sa.Unicode)
                updates[sa.cast(prop.name, sa.Unicode)] = value
        for column_name, updates in json_updates.items():
            column = getattr(cls, column_name)
            from .dialects.asyncpg import JSONB
            if isinstance(column.type, JSONB):
                if self._literal:
                    values[column_name] = column.concat(updates)
                else:
                    values[column_name] = column.concat(
                        sa.func.jsonb_build_object(
                            *itertools.chain(*updates.items())))
            else:
                raise TypeError(f'{column.type} is not supported.')

        opts = dict(return_model=False)
        if timeout is not DEFAULT:
            opts['timeout'] = timeout
        clause = self._clause.values(
            **values,
        ).returning(
            *[getattr(cls, key) for key in values],
        ).execution_options(**opts)
        if bind is None:
            bind = cls.__metadata__.bind
        row = await bind.first(clause)
        if not row:
            raise NoSuchRowError()
        self._instance.__values__.update(row)
        for prop in self._props:
            prop.reload(self._instance)
        return self

    def update(self, **values):
        """
        Set given attributes on the bound model instance, and add them into
        the update collections for :meth:`.apply`.

        Given keyword-only arguments are pairs of attribute names and values to
        update. This is not a coroutine, calling :meth:`.update` will have
        instant effect on the bound model instance - its in-memory values will
        be updated immediately. Therefore this can be used individually as a
        shortcut to update several attributes in a batch::

            user.update(age=32, disabled=True)

        :meth:`.update` returns ``self`` for chaining calls to either
        :meth:`.apply` or another :meth:`.update`. If one attribute is updated
        several times by the same :class:`.UpdateRequest`, then only the last
        value is remembered for :meth:`.apply`.

        Updated values can be SQLAlchemy expressions, for example an atomic
        increment for user balance looks like this::

            await user.update(balance=User.balance + 100).apply()

        .. note::

            Expression values will not affect the in-memory attribute value on
            :meth:`.update` before :meth:`.apply`, because it has no knowledge
            of the latest value in the database. After :meth:`.apply` the new
            value will be automatically reloaded from database with
            ``RETURNING`` clause.

        """

        cls = type(self._instance)
        for key, value in values.items():
            prop = cls.__dict__.get(key)
            if isinstance(prop, json_support.JSONProperty):
                value_from = '__profile__'
                method = self._set_prop
                k = prop
            else:
                value_from = '__values__'
                method = self._set
                k = key
            if not isinstance(value, ClauseElement):
                setattr(self._instance, key, value)
                value = getattr(self._instance, value_from)[key]
            method(k, value)
        return self


class CRUDModel(Model):
    """
    The base class for models with CRUD support.

    Don't inherit from this class directly, because it has no metadata. Use
    :attr:`db.Model <gino.api.Gino.Model>` instead.

    """

    query = _Query()
    """
    Get a SQLAlchemy query clause of the table behind this model. This equals
    to :func:`sqlalchemy.select([self.__table__])
    <sqlalchemy.sql.expression.select>`. If this attribute is retrieved on a
    model instance, then a where clause to locate this instance by its primary
    key is appended to the returning query clause. This model type is set as
    the execution option ``model`` in the returning clause, so by default the
    query yields instances of this model instead of database rows.
    
    """

    update = _Update()
    """
    This ``update`` behaves quite different on model classes rather than model
    instances.
    
    On model classes, ``update`` is an attribute of type
    :class:`~sqlalchemy.sql.expression.Update` for massive updates, for
    example::
    
        await User.update.values(enabled=True).where(...).gino.status()
    
    Like :attr:`.query`, the update query also has the ``model`` execution 
    option of this model, so if you use the
    :meth:`~sqlalchemy.sql.expression.Update.returning` clause, the query shall
    return model objects.
    
    However on model instances, ``update()`` is a method which accepts keyword
    arguments only and returns an :class:`.UpdateRequest` to update this single
    model instance. The keyword arguments are pairs of attribute names and new
    values. This is the same as :meth:`.UpdateRequest.update`, feel free to
    read more about it. A normal usage example would be like this::
    
        await user.update(name='new name', age=32).apply()
    
    Here, the :meth:`await ... apply() <.UpdateRequest.apply>` executes the
    actual ``UPDATE`` SQL in the database, while ``user.update()`` only makes
    changes in the memory, and collect all changes into an
    :class:`.UpdateRequest` instance.
    
    """

    delete = _Delete()
    """
    Similar to :meth:`.update`, this ``delete`` is also different on model
    classes than on model instances.
    
    On model classes ``delete`` is an attribute of type
    :class:`~sqlalchemy.sql.expression.Delete` for massive deletes, for
    example::
    
        await User.delete.where(User.enabled.is_(False)).gino.status()
        
    Similarly you can add a :meth:`~sqlalchemy.sql.expression.Delete.returning`
    clause to the query and it shall return the deleted rows as model objects.
    
    And on model instances, ``delete()`` is a method to remove the
    corresponding row in the database of this model instance. and returns the
    status returned from the database::
    
        print(await user.delete())  # e.g. prints DELETE 1
    
    .. note::
    
        ``delete()`` only removes the row from database, it does not affect the
        current model instance.
    
    :param bind: An optional :class:`~gino.engine.GinoEngine` if current
      metadata (:class:`~gino.api.Gino`) has no bound engine, or specifying a
      different :class:`~gino.engine.GinoEngine` to execute the ``DELETE``.
      
    :param timeout: Seconds to wait for the database to finish executing,
      ``None`` for wait forever. By default it will use the ``timeout``
      execution option value if unspecified.
    
    """

    select = _Select()
    """
    Build a query to retrieve only specified columns from this table.
    
    This method accepts positional string arguments as names of attributes to
    retrieve, and returns a :class:`~sqlalchemy.sql.expression.Select` for
    query. The returning query object is always set with two execution options:
    
    1. ``model`` is set to this model type
    2. ``return_model`` is set to ``False``
    
    So that by default it always return rows instead of model instances, while
    column types can be inferred correctly by the ``model`` option.
    
    For example::
    
        async for row in User.select('id', 'name').gino.iterate():
            print(row['id'], row['name'])
    
    If :meth:`.select` is invoked on a model instance, then a ``WHERE`` clause
    to locate this instance by its primary key is appended to the returning
    query clause. This is useful when you want to retrieve a latest value of a
    field on current model instance from database::
    
        db_age = await user.select('age').gino.scalar()
    
    .. seealso::
    
        :meth:`~gino.engine.GinoConnection.execution_options`
    
    """

    _update_request_cls = UpdateRequest

    def __init__(self, **values):
        super().__init__()
        self.__profile__ = None
        # noinspection PyCallingNonCallable
        self.update(**values)

    @classmethod
    def _init_table(cls, sub_cls):
        rv = Model._init_table(sub_cls)
        if rv is not None:
            rv.__model__ = weakref.ref(sub_cls)
        return rv

    @classmethod
    async def create(cls, bind=None, timeout=DEFAULT, **values):
        """
        Class method to create a new model instance and insert the row into
        database.

        Under the hood :meth:`.create` uses ``INSERT ... RETURNING ...`` to
        create the new model instance and load it with database default data if
        not specified.

        For example::

            user = await User.create(name='fantix', age=32)

        :param bind: A :class:`~gino.engine.GinoEngine` to execute the
          ``INSERT`` statement with, or ``None`` (default) to use the bound
          engine on the metadata (:class:`~gino.api.Gino`).

        :param timeout: Seconds to wait for the database to finish executing,
          ``None`` for wait forever. By default it will use the ``timeout``
          execution option value if unspecified.

        :param values: Keyword arguments are pairs of attribute names and their
          initial values.

        :return: An instance of this model class.

        """
        rv = cls(**values)

        # handle JSON properties
        props = []
        for key, value in values.items():
            prop = cls.__dict__.get(key)
            if isinstance(prop, json_support.JSONProperty):
                prop.save(rv)
                props.append(prop)
        for key, prop in cls.__dict__.items():
            if key in values:
                continue
            if isinstance(prop, json_support.JSONProperty):
                if prop.default is None or prop.after_get.method is not None:
                    continue
                setattr(rv, key, getattr(rv, key))
                prop.save(rv)
                props.append(prop)

        opts = dict(return_model=False, model=cls)
        if timeout is not DEFAULT:
            opts['timeout'] = timeout
        # noinspection PyArgumentList
        q = cls.__table__.insert().values(**rv.__values__).returning(
            *cls).execution_options(**opts)
        if bind is None:
            bind = cls.__metadata__.bind
        row = await bind.first(q)
        rv.__values__.update(row)
        rv.__profile__ = None
        return rv

    @classmethod
    async def get(cls, ident, bind=None, timeout=DEFAULT):
        """
        Get an instance of this model class by primary key.

        For example::

            user = await User.get(request.args.get('user_id'))

        :param ident: Value of the primary key. For composite primary keys this
          should be a tuple of values for all keys in database order.

        :param bind: A :class:`~gino.engine.GinoEngine` to execute the
          ``INSERT`` statement with, or ``None`` (default) to use the bound
          engine on the metadata (:class:`~gino.api.Gino`).

        :param timeout: Seconds to wait for the database to finish executing,
          ``None`` for wait forever. By default it will use the ``timeout``
          execution option value if unspecified.

        :return: An instance of this model class, or ``None`` if no such row.

        """
        if hasattr(ident, '__iter__'):
            ident_ = list(ident)
        else:
            ident_ = [ident]
        columns = cls.__table__.primary_key.columns
        if len(ident_) != len(columns):
            raise ValueError(
                'Incorrect number of values as primary key: '
                'expected {}, got {}.'.format(
                    len(columns), len(ident_)))
        clause = cls.query
        for i, c in enumerate(columns):
            clause = clause.where(c == ident_[i])
        if timeout is not DEFAULT:
            clause = clause.execution_options(timeout=timeout)
        if bind is None:
            bind = cls.__metadata__.bind
        return await bind.first(clause)

    def append_where_primary_key(self, q):
        """
        Append where clause to locate this model instance by primary on the
        given query, and return the new query.

        This is mostly used internally in GINO, but also available for such
        usage::

            await user.append_where_primary_key(User.query).gino.first()

        which is identical to::

            await user.query.gino.first()

        """
        for c in self.__table__.primary_key.columns:
            q = q.where(c == getattr(self, c.name))
        return q

    def _update(self, **values):
        return self._update_request_cls(self).update(**values)

    async def _delete(self, bind=None, timeout=DEFAULT):
        cls = type(self)
        clause = self.append_where_primary_key(cls.delete)
        if timeout is not DEFAULT:
            clause = clause.execution_options(timeout=timeout)
        if bind is None:
            bind = self.__metadata__.bind
        return (await bind.status(clause))[0]

    def to_dict(self):
        """
        Convenient method to generate a dict from this model instance.

        Keys will be attribute names, while values are loaded from memory (not
        from database). If there are :class:`~gino.json_support.JSONProperty`
        attributes in this model, their source JSON field will not be included
        in the returning dict - instead the JSON attributes will be.

        .. seealso::

            :mod:`.json_support`

        """
        cls = type(self)
        keys = set(c.name for c in cls)
        for key, prop in cls.__dict__.items():
            if isinstance(prop, json_support.JSONProperty):
                keys.add(key)
                keys.discard(prop.column_name)
        return dict((k, getattr(self, k)) for k in keys)
