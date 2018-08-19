import collections

import sqlalchemy as sa
from sqlalchemy.exc import InvalidRequestError

from .exceptions import GinoException


class ColumnAttribute:
    def __init__(self, prop_name, column):
        self.prop_name = prop_name
        self.column = column

    def __get__(self, instance, owner):
        if instance is None:
            return self.column
        else:
            return instance.__values__.get(self.prop_name)

    def __set__(self, instance, value):
        instance.__values__[self.prop_name] = value

    def __delete__(self, instance):
        raise AttributeError('Cannot delete value.')


class InvertDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._inverted_dict = dict()
        for k, v in self.items():
            if v in self._inverted_dict:
                raise GinoException(
                    'Column name {} already maps to {}'.format(
                        v, self._inverted_dict[v]))
            self._inverted_dict[v] = k

    def __setitem__(self, key, value):
        if value in self._inverted_dict and self._inverted_dict[value] != key:
            raise GinoException(
                'Column name {} already maps to {}'.format(
                    value, self._inverted_dict[value]))
        super().__setitem__(key, value)
        self._inverted_dict[value] = key

    def invert_get(self, key, default=None):
        return self._inverted_dict.get(key, default)


class ModelType(type):
    def _check_abstract(self):
        if self.__table__ is None:
            raise TypeError('GINO model {} is abstract, no table is '
                            'defined.'.format(self.__name__))

    def __iter__(self):
        self._check_abstract()
        # noinspection PyUnresolvedReferences
        return iter(self.__table__.columns)

    def __getattr__(self, item):
        try:
            if item in {'insert', 'join', 'outerjoin', 'gino'}:
                self._check_abstract()
                return getattr(self.__table__, item)
            raise AttributeError
        except AttributeError:
            raise AttributeError(
                "type object '{}' has no attribute '{}'".format(
                    self.__name__, item))

    @classmethod
    def __prepare__(mcs, name, bases, **kwargs):
        return collections.OrderedDict()

    def __new__(mcs, name, bases, namespace, **kwargs):
        rv = type.__new__(mcs, name, bases, namespace)
        rv.__namespace__ = namespace
        if rv.__table__ is None:
            rv.__table__ = getattr(rv, '_init_table')(rv)
        return rv


def declared_attr(m):
    """
    Mark a class-level method as a factory of attribute.

    This is intended to be used as decorators on class-level methods of a
    :class:`~Model` class. When initializing the class as well as its
    subclasses, the decorated factory method will be called for each class, the
    returned result will be set on the class in place of the factory method
    under the same name.

    ``@declared_attr`` is implemented differently than
    :class:`~sqlalchemy.ext.declarative.declared_attr` of SQLAlchemy, but they
    are both more often used on mixins to dynamically declare indices or
    constraints (also works for column and ``__table_args__``, or even normal
    class attributes)::

        class TrackedMixin:
            created = db.Column(db.DateTime(timezone=True))

            @db.declared_attr
            def unique_id(cls):
                return db.Column(db.Integer())

            @db.declared_attr
            def unique_constraint(cls):
                return db.UniqueConstraint('unique_id')

            @db.declared_attr
            def poly(cls):
                if cls.__name__ == 'Thing':
                    return db.Column(db.Unicode())

            @db.declared_attr
            def __table_args__(cls):
                if cls.__name__ == 'Thing':
                    return db.UniqueConstraint('poly'),

    .. note::

        This doesn't work if the model already had a ``__table__``.

    """
    m.__declared_attr__ = True
    return m


class Model:
    __metadata__ = None
    __table__ = None
    __attr_factory__ = ColumnAttribute

    def __init__(self):
        self.__values__ = {}

    @classmethod
    def _init_table(cls, sub_cls):
        table_name = getattr(sub_cls, '__tablename__', None)
        if table_name is None:
            return

        columns = []
        inspected_args = []
        updates = {}
        column_name_map = InvertDict()
        for each_cls in sub_cls.__mro__[::-1]:
            for k, v in getattr(each_cls, '__namespace__',
                                each_cls.__dict__).items():
                if callable(v) and getattr(v, '__declared_attr__', False):
                    v = updates[k] = v(sub_cls)
                if isinstance(v, sa.Column):
                    v = v.copy()
                    if not v.name:
                        v.name = k
                    column_name_map[k] = v.name
                    columns.append(v)
                    updates[k] = sub_cls.__attr_factory__(k, v)
                elif isinstance(v, (sa.Index, sa.Constraint)):
                    inspected_args.append(v)
        sub_cls._column_name_map = column_name_map

        # handle __table_args__
        table_args = updates.get('__table_args__',
                                 getattr(sub_cls, '__table_args__', None))
        args, table_kw = (), {}
        if isinstance(table_args, dict):
            table_kw = table_args
        elif isinstance(table_args, tuple) and table_args:
            if isinstance(table_args[-1], dict):
                args, table_kw = table_args[0:-1], table_args[-1]
            else:
                args = table_args

        args = (*columns, *inspected_args, *args)
        for item in args:
            try:
                _table = getattr(item, 'table', None)
            except InvalidRequestError:
                _table = None
            if _table is not None:
                raise ValueError(
                    '{} is already attached to another table. Please do not '
                    'use the same item twice. A common mistake is defining '
                    'constraints and indices in a super class - we are working'
                    ' on making it possible.')
        rv = sa.Table(table_name, sub_cls.__metadata__, *args, **table_kw)
        for k, v in updates.items():
            setattr(sub_cls, k, v)
        return rv


def declarative_base(metadata, model_classes=(Model,), name='Model'):
    return ModelType(name, model_classes, {'__metadata__': metadata})


# noinspection PyProtectedMember
@sa.inspection._inspects(ModelType)
def inspect_model_type(target):
    target._check_abstract()
    return sa.inspection.inspect(target.__table__)


__all__ = ['ColumnAttribute', 'Model', 'declarative_base', 'declared_attr',
           'InvertDict']
