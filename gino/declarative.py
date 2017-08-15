import itertools
import weakref

import sqlalchemy
import sqlalchemy.dialects.postgresql as sa_pg
from sqlalchemy import MetaData, Column, Table, select, text
from sqlalchemy import cutils

from . import json_support
from .dialect import AsyncpgDialect
from .asyncpg_delegate import AsyncpgMixin
from .exceptions import NotInstalledError, NoSuchRowError


class ColumnAttribute:
    def __init__(self, column):
        self.name = column.name
        self.column = column

    def __get__(self, instance, owner):
        if instance is None:
            return self.column
        else:
            return instance.__values__.get(self.name)

    def __set__(self, instance, value):
        if instance is None:
            raise AttributeError('Cannot change columns.')
        else:
            instance.__values__[self.name] = value

    def __delete__(self, instance):
        raise AttributeError('Cannot delete column or value.')


class Query:
    def __get__(self, instance, owner):
        q = select([owner.__table__])
        q.__model__ = weakref.ref(owner)
        if instance is not None:
            q = instance.append_where_primary_key(q)
        return q


class Update:
    def __get__(self, instance, owner):
        if instance is None:
            q = owner.__table__.update()
            q.__model__ = weakref.ref(owner)
            return q
        else:
            # noinspection PyProtectedMember
            return instance._update


class UpdateRequest:
    def __init__(self, instance):
        self._instance = instance
        self._values = {}
        self._props = {}
        self._literal = True
        self._clause = self._instance.append_where_primary_key(
            type(self._instance).update)

    def set(self, key, value):
        self._values[key] = value

    def set_prop(self, prop, value):
        if isinstance(value, sqlalchemy.sql.ClauseElement):
            self._literal = False
        self._props[prop] = value

    async def apply(self, bind=None, timeout=None):
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
                    value = sqlalchemy.cast(value, sqlalchemy.BigInteger)
                elif not isinstance(value, sqlalchemy.sql.ClauseElement):
                    value = sqlalchemy.cast(value, sqlalchemy.Unicode)
                updates[sqlalchemy.cast(prop.name, sqlalchemy.Unicode)] = value
        for column_name, updates in json_updates.items():
            column = getattr(cls, column_name)
            if self._literal:
                values[column_name] = column.concat(updates)
            else:
                if isinstance(column.type, sa_pg.JSONB):
                    func = sqlalchemy.func.jsonb_build_object
                else:
                    func = sqlalchemy.func.json_build_object
                values[column_name] = column.concat(
                    func(*itertools.chain(*updates.items())))

        # noinspection PyProtectedMember
        clause = self._clause.values(
            **values,
        ).returning(
            *[getattr(cls, key) for key in values],
        )
        query, args = cls.__metadata__.compile(clause)
        bind = await cls.__metadata__.get_bind(bind)
        row = await bind.fetchrow(query, *args, timeout=timeout)
        if not row:
            raise NoSuchRowError()
        self._instance.update_with_row(row)
        for prop in self._props:
            prop.reload(self._instance)
        return self


class Delete:
    def __get__(self, instance, owner):
        if instance is None:
            q = owner.__table__.delete()
            q.__model__ = weakref.ref(owner)
            return q
        else:
            # noinspection PyProtectedMember
            return instance._delete


class Model:
    __metadata__ = None
    __table__ = None
    query = Query()
    update = Update()
    delete = Delete()

    def __init__(self, **values):
        self.__values__ = {}
        self.__profile__ = None
        # noinspection PyCallingNonCallable
        self.update(**values)

    def __init_subclass__(cls, **kwargs):
        table_name = getattr(cls, '__tablename__', None)
        if table_name:
            columns = []
            updates = {}
            for k, v in cls.__dict__.items():
                if isinstance(v, Column):
                    v.name = k
                    columns.append(v)
                    updates[k] = ColumnAttribute(v)

            # handle __table_args__
            table_args = getattr(cls, '__table_args__', None)
            args, table_kw = (), {}
            if isinstance(table_args, dict):
                table_kw = table_args
            elif isinstance(table_args, tuple) and table_args:
                if isinstance(table_args[-1], dict):
                    args, table_kw = table_args[0:-1], table_args[-1]
                else:
                    args = table_args

            table = updates['__table__'] = Table(
                table_name, cls.__metadata__, *columns, *args, **table_kw)
            for k, v in updates.items():
                setattr(cls, k, v)
            table.__model__ = weakref.ref(cls)
        super().__init_subclass__()

    @classmethod
    def select(cls, *args):
        q = select([getattr(cls, x) for x in args])
        q.__model__ = weakref.ref(cls)
        return q

    @classmethod
    async def create(cls, bind=None, timeout=None, **values):
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

        q = cls.__table__.insert().values(**rv.__values__).returning(text('*'))
        bind = await cls.__metadata__.get_bind(bind)
        query, args = cls.__metadata__.compile(q)
        row = await bind.fetchrow(query, *args, timeout=timeout)
        rv.update_with_row(row)
        rv.__profile__ = None
        return rv

    @classmethod
    async def get(cls, ident, bind=None, timeout=None):
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
        return await cls.__metadata__.first(clause, bind=bind, timeout=timeout)

    @classmethod
    async def get_or_404(cls, id_, bind=None, timeout=None):
        try:
            from sanic.exceptions import NotFound
        except ModuleNotFoundError:
            raise NotInstalledError('Sanic has not been installed yet.')

        rv = await cls.get(id_, bind=bind, timeout=timeout)
        if rv is None:
            # noinspection PyPackageRequirements
            raise NotFound('{} is not found'.format(cls.__name__))
        return rv

    @classmethod
    async def map(cls, iterable):
        async for row in iterable:
            yield cls.from_row(row)

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls().update_with_row(row)

    @classmethod
    def cached_result_processor(cls, col):
        if isinstance(col, str):
            col = getattr(cls, col)
        # noinspection PyProtectedMember
        return col.type._cached_result_processor(cls.__metadata__.dialect,
                                                 None)

    def append_where_primary_key(self, q):
        for c in self.__table__.primary_key.columns:
            q = q.where(c == getattr(self, c.name))
        return q

    def update_with_row(self, row):
        for key, value in row.items():
            processor = self.cached_result_processor(key)
            if processor:
                value = processor(value)
            setattr(self, key, value)
        return self

    def _update(self, **values):
        cls = type(self)
        rv = UpdateRequest(self)
        for key, value in values.items():
            prop = cls.__dict__.get(key)
            if isinstance(prop, json_support.JSONProperty):
                value_from = '__profile__'
                method = rv.set_prop
                k = prop
            else:
                value_from = '__values__'
                method = rv.set
                k = key
            if not isinstance(value, sqlalchemy.sql.ClauseElement):
                setattr(self, key, value)
                value = getattr(self, value_from)[key]
            method(k, value)
        return rv

    async def _delete(self, bind=None):
        cls = type(self)
        clause = self.append_where_primary_key(cls.delete)
        return await self.__metadata__.status(clause, bind=bind)


class NoopConnection:
    def __init__(self, dialect):
        self.dialect = dialect
        self._execution_options = {}

    def cursor(self):
        pass


class Gino(MetaData, AsyncpgMixin):
    def __init__(self, bind=None, dialect=None, **kwargs):
        self._bind = None
        super().__init__(bind=bind, **kwargs)
        self.dialect = dialect or AsyncpgDialect()
        self.Model = type('Model', (Model,), {'__metadata__': self})

        for mod in sqlalchemy, sa_pg, json_support:
            for key in mod.__all__:
                if not hasattr(self, key):
                    setattr(self, key, getattr(mod, key))

    def compile(self, elem, *multiparams, **params):
        # partially copied from:
        # sqlalchemy.engine.base.Connection:_execute_clauseelement
        # noinspection PyProtectedMember,PyUnresolvedReferences
        distilled_params = cutils._distill_params(multiparams, params)
        if distilled_params:
            # note this is usually dict but we support RowProxy
            # as well; but dict.keys() as an iterable is OK
            keys = distilled_params[0].keys()
        else:
            keys = []
        dialect = self.dialect
        compiled_sql = elem.compile(
            dialect=dialect, column_keys=keys,
            inline=len(distilled_params) > 1,
        )
        conn = NoopConnection(self.dialect)
        # noinspection PyProtectedMember
        context = dialect.execution_ctx_cls._init_compiled(
            dialect, conn, conn, compiled_sql, distilled_params)
        return context.statement, context.parameters[0]

    @classmethod
    def guess_model(cls, query):
        # query.__model__ is weak references, which need dereference
        model = getattr(query, '__model__', lambda: None)()
        if model is not None:
            return model
        tables = getattr(query, 'froms', [])
        if len(tables) != 1:
            return
        model = getattr(tables[0], '__model__', lambda: None)()
        if not model:
            return
        for c in query.columns:
            if not hasattr(model, c.name):
                return
        return model

    @property
    def bind(self):
        return self._bind

    # noinspection PyMethodOverriding
    @bind.setter
    def bind(self, val):
        self._bind = val
