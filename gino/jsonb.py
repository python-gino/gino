from datetime import datetime

import sqlalchemy as sa

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


class _None:
    pass


class _Wrapper:
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


# noinspection PyPep8Naming
class json_property:
    def __init__(self, default_factory=None, default=None):
        self.name = None
        self.default_factory = default_factory
        self.default = default
        self.expression = _Wrapper(self)
        self.after_get = _Wrapper(self)
        self.before_set = _Wrapper(self)

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self.expression.call(owner, owner.profile[self.name])
        val = instance.profile.get(self.name, _None)
        if val is _None:
            if self.default_factory is None:
                val = self.default
            else:
                val = self.default_factory(instance)
        return self.after_get.call(instance, val)

    def __set__(self, instance, value):
        instance.profile[self.name] = self.before_set.call(instance, value)

    def __delete__(self, instance):
        instance.profile.pop(self.name, None)


# noinspection PyPep8Naming
class string_property(json_property):
    def __init__(self, default_factory):
        super().__init__(default_factory)
        self.expression(lambda *x: x[1].astext)


# noinspection PyPep8Naming
class datetime_property(json_property):
    def __init__(self, default_factory):
        super().__init__(default_factory)
        self.expression(lambda *x: x[1].astext.cast(sa.DateTime))
        self.after_get(self.getter)
        self.before_set(self.setter)

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def getter(self, instance, val):
        if val:
            val = datetime.strptime(val, DATETIME_FORMAT)
        return val

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def setter(self, instance, val):
        if isinstance(val, datetime):
            val = val.strftime(DATETIME_FORMAT)
        return val


# noinspection PyPep8Naming
class integer_property(json_property):
    def __init__(self, default_factory):
        super().__init__(default_factory)
        self.expression(lambda *x: x[1].astext.cast(sa.Integer))
        self.after_get(self.getter)
        self.before_set(self.setter)

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def getter(self, instance, val):
        if val is not None:
            val = int(val)
        return val

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def setter(self, instance, val):
        if val is not None:
            val = int(val)
        return val


# noinspection PyPep8Naming
class bool_property(json_property):
    def __init__(self, default_factory):
        super().__init__(default_factory)
        self.expression(lambda *x: x[1].astext.cast(sa.Boolean))
        self.after_get(lambda *x: bool(x[1]))
        self.before_set(lambda *x: bool(x[1]))


# noinspection PyPep8Naming
class object_property(json_property):
    def __init__(self, default_factory):
        super().__init__(default_factory)
        self.after_get(lambda *x: dict(x[1]))
        self.before_set(lambda *x: dict(x[1]))


# noinspection PyPep8Naming
class array_property(json_property):
    def __init__(self, default_factory):
        super().__init__(default_factory)
        self.after_get(lambda *x: list(x[1]))
        self.before_set(lambda *x: list(x[1]))
