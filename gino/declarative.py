from sqlalchemy import MetaData, Column, Table, select
from sqlalchemy import cutils

from .dialect import AsyncpgDialect


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
        return select([owner.__table__])


class Gino(MetaData):
    def __init__(self, dialect=None, **kwargs):
        kwargs['bind'] = None
        super().__init__(**kwargs)
        self.dialect = dialect or AsyncpgDialect()
        metadata = self

        class ModelType(type):
            # noinspection PyInitNewSignature
            def __new__(mcs, name, bases, namespace, **new_kwargs):
                table_name = namespace.get('__tablename__')
                if table_name and metadata:
                    columns = []
                    updates = {}
                    for k, v in namespace.items():
                        if isinstance(v, Column):
                            v.name = k
                            columns.append(v)
                            updates[k] = ColumnAttribute(v)
                    updates['__table__'] = Table(
                        table_name, metadata, *columns)
                    namespace.update(updates)
                return type.__new__(mcs, name, bases, namespace)

        class Model(metaclass=ModelType):
            __values__ = {}
            __table__ = None
            query = Query()

            def __init__(self, **values):
                self.update(**values)

            @classmethod
            def select(cls, *args):
                return select([getattr(cls, x) for x in args])

            @classmethod
            async def create(cls, conn, **values):
                # noinspection PyUnresolvedReferences
                clause = cls.__table__.insert().values(**values).returning(
                    cls.id)
                query, params = metadata.compile(clause)
                values['id'] = await conn.fetchval(query, *params)
                return cls(**values)

            @classmethod
            async def get(cls, conn, id_):
                # noinspection PyUnresolvedReferences
                clause = cls.query.where(cls.id == id_)
                query, params = metadata.compile(clause)
                row = await conn.fetchrow(query, *params)
                if row is None:
                    return None
                return cls(**row)

            @classmethod
            async def get_or_404(cls, conn, id_):
                rv = await cls.get(conn, id_)
                if rv is None:
                    # noinspection PyPackageRequirements
                    from sanic.exceptions import NotFound
                    raise NotFound('{} is not found'.format(cls.__name__))
                return rv

            @classmethod
            async def map(cls, iterable):
                async for row in iterable:
                    yield cls(**row)

            def update(self, **values):
                for attr, value in values.items():
                    setattr(self, attr, value)

        self.Model = Model

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
        # noinspection PyProtectedMember
        context = dialect.execution_ctx_cls._init_compiled(
            dialect, compiled_sql, distilled_params)
        return context.statement, context.parameters[0]
