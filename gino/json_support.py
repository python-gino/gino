from datetime import datetime

import sqlalchemy as sa

DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'
NONE = object()


class Hook:
    def __init__(self, parent):
        self.parent = parent
        self.method = None

    def __call__(self, method):
        self.method = method
        return self.parent

    def call(self, instance, val):
        if self.method is not None:
            val = self.method(instance, val)
        return val


class JSONProperty:
    def __init__(self, default=None, column_name='profile'):
        self.name = None
        self.default = default
        self.column_name = column_name
        self.expression = Hook(self)
        self.after_get = Hook(self)
        self.before_set = Hook(self)

    def __set_name__(self, owner, name):
        if not hasattr(owner, self.column_name):
            raise AttributeError(
                f'Requires "{self.column_name}" JSON[B] column.')
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            exp = self.make_expression(
                getattr(owner, self.column_name)[self.name])
            return self.expression.call(owner, exp)
        val = self.get_profile(instance).get(self.name, NONE)
        if val is NONE:
            if callable(self.default):
                val = self.default(instance)
            else:
                val = self.default
        return self.after_get.call(instance, val)

    def __set__(self, instance, value):
        self.get_profile(instance)[self.name] = self.before_set.call(
            instance, value)

    def __delete__(self, instance):
        self.get_profile(instance).pop(self.name, None)

    def get_profile(self, instance):
        if instance.__profile__ is None:
            props = type(instance).__dict__
            instance.__profile__ = {}
            for key, value in (getattr(instance, self.column_name, None)
                               or {}).items():
                instance.__profile__[key] = props[key].decode(value)
        return instance.__profile__

    def save(self, instance, value=NONE):
        profile = getattr(instance, self.column_name, None)
        if profile is None:
            profile = {}
            setattr(instance, self.column_name, profile)
        if value is NONE:
            value = instance.__profile__[self.name]
        if not isinstance(value, sa.sql.ClauseElement):
            value = self.encode(value)
        rv = profile[self.name] = value
        return rv

    def reload(self, instance):
        profile = getattr(instance, self.column_name, None) or {}
        value = profile.get(self.name, NONE)
        if value is NONE:
            instance.__profile__.pop(self.name, None)
        else:
            instance.__profile__[self.name] = self.decode(value)

    def make_expression(self, base_exp):
        return base_exp

    def decode(self, val):
        return val

    def encode(self, val):
        return val

    def __hash__(self):
        return hash(self.name)


class StringProperty(JSONProperty):
    def make_expression(self, base_exp):
        return base_exp.astext


class DateTimeProperty(JSONProperty):
    def make_expression(self, base_exp):
        return base_exp.astext.cast(sa.DateTime)

    def decode(self, val):
        if val:
            val = datetime.strptime(val, DATETIME_FORMAT)
        return val

    def encode(self, val):
        if isinstance(val, datetime):
            val = val.strftime(DATETIME_FORMAT)
        return val


class IntegerProperty(JSONProperty):
    def make_expression(self, base_exp):
        return base_exp.astext.cast(sa.Integer)

    def decode(self, val):
        if val is not None:
            val = int(val)
        return val

    def encode(self, val):
        if val is not None:
            val = int(val)
        return val


class BooleanProperty(JSONProperty):
    def make_expression(self, base_exp):
        return base_exp.astext.cast(sa.Boolean)

    def decode(self, val):
        if val is not None:
            val = bool(val)
        return val

    def encode(self, val):
        if val is not None:
            val = bool(val)
        return val


class ObjectProperty(JSONProperty):
    def decode(self, val):
        if val is not None:
            val = dict(val)
        return val

    def encode(self, val):
        if val is not None:
            val = dict(val)
        return val


class ArrayProperty(JSONProperty):
    def decode(self, val):
        if val is not None:
            val = list(val)
        return val

    def encode(self, val):
        if val is not None:
            val = list(val)
        return val


__all__ = ['JSONProperty', 'StringProperty', 'DateTimeProperty',
           'IntegerProperty', 'BooleanProperty', 'ObjectProperty',
           'ArrayProperty']
