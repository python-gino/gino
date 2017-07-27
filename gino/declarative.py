from sqlalchemy import MetaData, Column, Table, select
from sqlalchemy import cutils

from .dialect import AsyncpgDialect
from .asyncpg_delegate import AsyncpgMixin


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
        q.__model__ = owner
        return q


class ModelType(type):
    metadata = None

    # noinspection PyInitNewSignature
    def __new__(mcs, name, bases, namespace, **new_kwargs):
        table = None
        table_name = namespace.get('__tablename__')
        if table_name:
            columns = []
            updates = {}
            for k, v in namespace.items():
                if isinstance(v, Column):
                    v.name = k
                    columns.append(v)
                    updates[k] = ColumnAttribute(v)
            table = updates['__table__'] = Table(
                table_name, mcs.metadata, *columns)
            namespace.update(updates)
        rv = type.__new__(mcs, name, bases, namespace)
        if table is not None:
            table.__model__ = rv
        return rv


class Model(metaclass=ModelType):
    __metadata__ = None
    __table__ = None
    query = Query()

    def __init__(self, **values):
        self.__values__ = {}
        self.update(**values)

    @classmethod
    def select(cls, *args):
        q = select([getattr(cls, x) for x in args])
        q.__model__ = cls
        return q

    @classmethod
    async def create(cls, bind=None, **values):
        # noinspection PyUnresolvedReferences
        clause = cls.__table__.insert().values(**values).returning(cls.id)
        values['id'] = await cls.__metadata__.scalar(clause, bind=bind)
        return cls(**values)

    @classmethod
    async def get(cls, id_, bind=None):
        # noinspection PyUnresolvedReferences
        clause = cls.query.where(cls.id == id_)
        return await cls.__metadata__.first(clause, bind=bind)

    @classmethod
    async def get_or_404(cls, id_, bind=None):
        rv = await cls.get(id_, bind=bind)
        if rv is None:
            # noinspection PyPackageRequirements
            from sanic.exceptions import NotFound
            raise NotFound('{} is not found'.format(cls.__name__))
        return rv

    @classmethod
    async def map(cls, iterable):
        async for row in iterable:
            yield cls.from_row(row)

    @classmethod
    def from_row(cls, row):
        return cls(**row)

    def update(self, **values):
        for attr, value in values.items():
            setattr(self, attr, value)


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
        model_type = type('ModelType', (ModelType,), {'metadata': self})
        self.Model = model_type('Model', (Model,), {'__metadata__': self})

    def compile(self, elem, *multiparams, **params):
        # partially copied from:
        # sqlalchemy.engine.base.Connection:_execute_clauseelement
        # noinspection PyProtectedMember
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
        model = getattr(query, '__model__', None)
        if model is not None:
            return model
        tables = query.froms
        if len(tables) != 1:
            return
        model = getattr(tables[0], '__model__', None)
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
