from sqlalchemy.dialects.postgresql.base import (
    PGCompiler,
    PGDialect,
    PGExecutionContext,
)


# noinspection PyAbstractClass
class AsyncpgExecutionContext(PGExecutionContext):
    # noinspection PyMethodOverriding
    @classmethod
    def _init_compiled(cls, dialect, compiled, parameters):
        class _Conn:
            def __init__(self):
                self.dialect = dialect
                self._execution_options = None

        class _DBConn:
            def cursor(self):
                pass

        return super()._init_compiled(dialect, _Conn(), _DBConn(), compiled,
                                      parameters)


class AsyncpgCompiler(PGCompiler):
    @property
    def bindtemplate(self):
        return self._bindtemplate

    @bindtemplate.setter
    def bindtemplate(self, val):
        # noinspection PyAttributeOutsideInit
        self._bindtemplate = val.replace(':', '$')


# noinspection PyAbstractClass
class AsyncpgDialect(PGDialect):
    default_paramstyle = 'numeric'
    statement_compiler = AsyncpgCompiler
    execution_ctx_cls = AsyncpgExecutionContext
