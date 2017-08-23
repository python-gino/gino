from sqlalchemy import cutils
from sqlalchemy.dialects.postgresql.base import (
    PGCompiler,
    PGDialect,
)


class AsyncpgCompiler(PGCompiler):
    @property
    def bindtemplate(self):
        return self._bindtemplate

    @bindtemplate.setter
    def bindtemplate(self, val):
        # noinspection PyAttributeOutsideInit
        self._bindtemplate = val.replace(':', '$')


class NoopConnection:
    def __init__(self, dialect):
        self.dialect = dialect
        self._execution_options = {}

    def cursor(self):
        pass


# noinspection PyAbstractClass
class AsyncpgDialect(PGDialect):
    default_paramstyle = 'numeric'
    statement_compiler = AsyncpgCompiler

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
        compiled_sql = elem.compile(
            dialect=self, column_keys=keys,
            inline=len(distilled_params) > 1,
        )
        conn = NoopConnection(self)
        # noinspection PyProtectedMember
        context = self.execution_ctx_cls._init_compiled(
            self, conn, conn, compiled_sql, distilled_params)
        return context.statement, context.parameters[0]

    def get_result_processor(self, col):
        # noinspection PyProtectedMember
        return col.type._cached_result_processor(self, None)
