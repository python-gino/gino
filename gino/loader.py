from sqlalchemy.schema import Column
from .declarative import Model


class Loader:
    one = True

    @classmethod
    def get(cls, value):
        if isinstance(value, Loader):
            rv = value
        elif isinstance(value, type) and issubclass(value, Model):
            rv = ModelLoader(value)
        elif isinstance(value, Column):
            rv = ColumnLoader(value)
        elif isinstance(value, tuple):
            rv = TupleLoader(value)
        elif callable(value):
            rv = CallableLoader(value)
        else:
            rv = ValueLoader(value)
        return rv

    def load(self, row, context):
        raise NotImplementedError


class ModelLoader(Loader):
    def __init__(self, model, *column_names, **relationships):
        self.model = model
        if column_names:
            self.columns = [getattr(model, name) for name in column_names]
        else:
            self.columns = model
        self.relationships = dict((key, self.get(value))
                                  for key, value in relationships.items())

    def load(self, row, context):
        rv = self.model()
        for c in self.columns:
            rv.__values__[c.name] = row[c]
        for key, value in self.relationships.items():
            setattr(rv, key, value.load(row, rv))
        return rv


class ColumnLoader(Loader):
    def __init__(self, column):
        self.column = column

    def load(self, row, context):
        return row[self.column]


class TupleLoader(Loader):
    def __init__(self, values):
        self.loaders = (self.get(value) for value in values)

    def load(self, row, context):
        return tuple(loader.load(row, context) for loader in self.loaders)


class CallableLoader(Loader):
    def __init__(self, func):
        self.func = func

    def load(self, row, context):
        return self.func(row, context)


class ValueLoader(Loader):
    def __init__(self, value):
        self.value = value

    def load(self, row, context):
        return self.value
