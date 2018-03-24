import sqlalchemy as sa


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
        instance.__values__[self.name] = value

    def __delete__(self, instance):
        raise AttributeError('Cannot delete value.')


class ModelType(type):
    def __iter__(self):
        # noinspection PyUnresolvedReferences
        return iter(self.__table__.columns)

    def __getattr__(self, item):
        try:
            if item in {'insert', 'join', 'outerjoin', 'gino'}:
                return getattr(self.__table__, item)
            raise AttributeError
        except AttributeError:
            raise AttributeError(
                "type object '{}' has no attribute '{}'".format(
                    self.__name__, item))


class Model:
    __metadata__ = None
    __table__ = None
    __attr_factory__ = ColumnAttribute

    def __init__(self):
        self.__values__ = {}

    def __init_subclass__(cls, **kwargs):
        if cls.__table__ is None:
            cls.__table__ = cls._init_table(cls)

    @classmethod
    def _init_table(cls, sub_cls):
        table_name = getattr(sub_cls, '__tablename__', None)
        if table_name is None:
            return

        columns = []
        updates = {}
        for each_cls in sub_cls.__mro__[::-1]:
            for k, v in each_cls.__dict__.items():
                if isinstance(v, sa.Column):
                    v = v.copy()
                    v.name = k
                    columns.append(v)
                    updates[k] = sub_cls.__attr_factory__(v)

        # handle __table_args__
        table_args = getattr(sub_cls, '__table_args__', None)
        args, table_kw = (), {}
        if isinstance(table_args, dict):
            table_kw = table_args
        elif isinstance(table_args, tuple) and table_args:
            if isinstance(table_args[-1], dict):
                args, table_kw = table_args[0:-1], table_args[-1]
            else:
                args = table_args

        rv = sa.Table(table_name, sub_cls.__metadata__,
                      *columns, *args, **table_kw)
        for k, v in updates.items():
            setattr(sub_cls, k, v)
        return rv


def declarative_base(metadata, model_classes=(Model,), name='Model'):
    return ModelType(name, model_classes, {'__metadata__': metadata})


# noinspection PyProtectedMember
@sa.inspection._inspects(ModelType)
def inspect_model_type(target):
    return sa.inspection.inspect(target.__table__)


__all__ = ['ColumnAttribute', 'Model', 'declarative_base']
