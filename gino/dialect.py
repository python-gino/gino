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


# noinspection PyAbstractClass
class AsyncpgDialect(PGDialect):
    default_paramstyle = 'numeric'
    statement_compiler = AsyncpgCompiler
