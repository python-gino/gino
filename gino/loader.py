from sqlalchemy import select
from sqlalchemy.schema import Column

from .declarative import Model


class Loader:
    @classmethod
    def get(cls, value):
        from .crud import Alias

        if isinstance(value, Loader):
            rv = value
        elif isinstance(value, type) and issubclass(value, Model):
            rv = ModelLoader(value)
        elif isinstance(value, Alias):
            rv = AliasLoader(value)
        elif isinstance(value, Column):
            rv = ColumnLoader(value)
        elif isinstance(value, tuple):
            rv = TupleLoader(value)
        elif callable(value):
            rv = CallableLoader(value)
        else:
            rv = ValueLoader(value)
        return rv

    @property
    def query(self):
        rv = select(self.get_columns())
        from_clause = self.get_from()
        if from_clause is not None:
            rv = rv.select_from(from_clause)
        return rv.execution_options(loader=self)

    def do_load(self, row, context):
        raise NotImplementedError

    def get_columns(self):
        return []

    def get_from(self):
        return None

    def __getattr__(self, item):
        return getattr(self.query, item)


class ModelLoader(Loader):
    def __init__(self, model, *column_names, **extras):
        self.model = model
        self._distinct = None
        if column_names:
            self.columns = [getattr(model, name) for name in column_names]
        else:
            self.columns = model
        self.extras = dict((key, self.get(value))
                           for key, value in extras.items())
        self.on_clause = None

    def _do_load(self, row):
        rv = self.model()
        for c in self.columns:
            if c in row:
                rv.__values__[c.name] = row[c]
        return rv

    def do_load(self, row, context):
        distinct = True
        if self._distinct:
            if context is None:
                context = {}
            ctx = context.setdefault(self._distinct, {})
            key = tuple(row[col] for col in self._distinct)
            if key == (None,) * len(key):
                return None, None
            rv = ctx.get(key)
            if rv is None:
                rv = self._do_load(row)
                ctx[key] = rv
            else:
                distinct = False
        else:
            rv = self._do_load(row)

        for key, value in self.extras.items():
            value, distinct_ = value.do_load(row, context)
            if distinct_ is not None:
                setattr(rv, key, value)
        return rv, distinct

    def get_columns(self):
        yield from self.columns
        for subloader in self.extras.values():
            yield from subloader.get_columns()

    def get_from(self):
        rv = self.model
        for key, subloader in self.extras.items():
            from_clause = subloader.get_from()
            if from_clause is not None:
                rv = rv.outerjoin(from_clause,
                                  getattr(subloader, 'on_clause', None))
        return rv

    def load(self, *column_names, **extras):
        if column_names:
            self.columns = [getattr(self.model, name) for name in column_names]
        self.extras.update((key, self.get(value))
                           for key, value in extras.items())
        return self

    def on(self, on_clause):
        self.on_clause = on_clause
        return self

    def distinct(self, *columns):
        self._distinct = columns
        return self


class AliasLoader(ModelLoader):
    def __init__(self, alias, *column_names, **extras):
        super().__init__(alias, *column_names, **extras)


class ColumnLoader(Loader):
    def __init__(self, column):
        self.column = column

    def do_load(self, row, context):
        return row[self.column], True


class TupleLoader(Loader):
    def __init__(self, values):
        self.loaders = (self.get(value) for value in values)

    def do_load(self, row, context):
        return tuple(loader.do_load(row, context)[0]
                     for loader in self.loaders), True


class CallableLoader(Loader):
    def __init__(self, func):
        self.func = func

    def do_load(self, row, context):
        return self.func(row, context), True


class ValueLoader(Loader):
    def __init__(self, value):
        self.value = value

    def do_load(self, row, context):
        return self.value, True
