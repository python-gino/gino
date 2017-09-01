import itertools
import weakref

import sqlalchemy as sa
from sqlalchemy.sql import ClauseElement
from sqlalchemy.dialects import postgresql as sa_pg

from . import json_support
from .declarative import Model
from .exceptions import NoSuchRowError

DEFAULT = object()


class Query:
    def __get__(self, instance, owner):
        q = sa.select([owner.__table__])
        if instance is not None:
            q = instance.append_where_primary_key(q)
        return q.execution_options(model=weakref.ref(owner))


class Select:
    def __get__(self, instance, owner):
        def select(*args):
            q = sa.select([getattr(owner, x) for x in args])
            if instance is not None:
                q = instance.append_where_primary_key(q)
            return q.execution_options(model=weakref.ref(owner),
                                       return_model=False)
        return select


class Update:
    def __get__(self, instance, owner):
        if instance is None:
            q = owner.__table__.update()
            return q.execution_options(model=weakref.ref(owner))
        else:
            # noinspection PyProtectedMember
            return instance._update


class Delete:
    def __get__(self, instance, owner):
        if instance is None:
            q = owner.__table__.delete()
            return q.execution_options(model=weakref.ref(owner))
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

    async def apply(self, bind=None, timeout=DEFAULT):
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

        opts = dict(return_model=False)
        if timeout is not DEFAULT:
            opts['timeout'] = timeout
        clause = self._clause.values(
            **values,
        ).returning(
            *[getattr(cls, key) for key in values],
        ).execution_options(**opts)
        row = await cls.__metadata__.first(clause, bind=bind)
        if not row:
            raise NoSuchRowError()
        self._instance.__values__.update(row)
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
    async def create(cls, bind=None, timeout=DEFAULT, **values):
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
        q = cls.__table__.insert().values(**rv.__values__).returning(
            sa.text('*')).execution_options(**opts)
        row = await cls.__metadata__.first(q, bind=bind)
        rv.__values__.update(row)
        rv.__profile__ = None
        return rv

    @classmethod
    async def get(cls, ident, bind=None, timeout=DEFAULT):
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
        return await cls.__metadata__.first(clause, bind=bind)

    def append_where_primary_key(self, q):
        for c in self.__table__.primary_key.columns:
            q = q.where(c == getattr(self, c.name))
        return q

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

    async def _delete(self, bind=None, timeout=DEFAULT):
        cls = type(self)
        clause = self.append_where_primary_key(cls.delete)
        if timeout is not DEFAULT:
            clause = clause.execution_options(timeout=timeout)
        return await self.__metadata__.status(clause, bind=bind)

    def to_dict(self):
        cls = type(self)
        keys = set(c.name for c in cls)
        for key, prop in cls.__dict__.items():
            if isinstance(prop, json_support.JSONProperty):
                keys.add(key)
                keys.discard(prop.column_name)
        return dict((k, getattr(self, k)) for k in keys)
