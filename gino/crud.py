import itertools
import weakref

import sqlalchemy as sa
from sqlalchemy.sql import ClauseElement
from sqlalchemy.dialects import postgresql as sa_pg

from . import json_support
from .declarative import Model
from .exceptions import NotInstalledError, NoSuchRowError


class Query:
    def __get__(self, instance, owner):
        q = sa.select([owner.__table__])
        q.__model__ = weakref.ref(owner)
        if instance is not None:
            q = instance.append_where_primary_key(q)
        return q


class Select:
    def __get__(self, instance, owner):
        def select(*args):
            q = sa.select([getattr(owner, x) for x in args])
            q.__model__ = weakref.ref(owner)
            if instance is not None:
                q = instance.append_where_primary_key(q)
            return q
        return select


class Update:
    def __get__(self, instance, owner):
        if instance is None:
            q = owner.__table__.update()
            q.__model__ = weakref.ref(owner)
            return q
        else:
            # noinspection PyProtectedMember
            return instance._update


class Delete:
    def __get__(self, instance, owner):
        if instance is None:
            q = owner.__table__.delete()
            q.__model__ = weakref.ref(owner)
            return q
        else:
            # noinspection PyProtectedMember
            return instance._delete


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
        if isinstance(value, ClauseElement):
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
                    value = sa.cast(value, sa.BigInteger)
                elif not isinstance(value, ClauseElement):
                    value = sa.cast(value, sa.Unicode)
                updates[sa.cast(prop.name, sa.Unicode)] = value
        for column_name, updates in json_updates.items():
            column = getattr(cls, column_name)
            if self._literal:
                values[column_name] = column.concat(updates)
            else:
                if isinstance(column.type, sa_pg.JSONB):
                    func = sa.func.jsonb_build_object
                else:
                    func = sa.func.json_build_object
                values[column_name] = column.concat(
                    func(*itertools.chain(*updates.items())))

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


class CRUDModel(Model):
    query = Query()
    update = Update()
    delete = Delete()
    select = Select()

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
    async def map(cls, iterable):
        async for row in iterable:
            yield cls.from_row(row)

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        return cls().update_with_row(row)

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

        q = cls.__table__.insert().values(**rv.__values__).returning(
            sa.text('*'))
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
            # noinspection PyPackageRequirements
            from sanic.exceptions import NotFound
        except ModuleNotFoundError:
            raise NotInstalledError('Sanic has not been installed yet.')

        rv = await cls.get(id_, bind=bind, timeout=timeout)
        if rv is None:
            raise NotFound('{} is not found'.format(cls.__name__))
        return rv

    def append_where_primary_key(self, q):
        for c in self.__table__.primary_key.columns:
            q = q.where(c == getattr(self, c.name))
        return q

    def update_with_row(self, row):
        cls = type(self)
        dialect = self.__metadata__.dialect
        for key, value in row.items():
            processor = dialect.get_result_processor(getattr(cls, key))
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
            if not isinstance(value, ClauseElement):
                setattr(self, key, value)
                value = getattr(self, value_from)[key]
            method(k, value)
        return rv

    async def _delete(self, bind=None):
        cls = type(self)
        clause = self.append_where_primary_key(cls.delete)
        return await self.__metadata__.status(clause, bind=bind)


def guess_model(query):
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
