from asyncpg.connection import Connection

from .dialect import GinoCursorFactory


class GinoConnection(Connection):
    __slots__ = ('_metadata', '_execution_options')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._metadata = None
        self._execution_options = {}

    def _set_metadata(self, metadata):
        self._metadata = metadata

    @property
    def metadata(self):
        return self._metadata

    @property
    def execution_options(self):
        return self._execution_options

    @property
    def dialect(self):
        return self._metadata.dialect

    async def all(self, clause, *multiparams, **params):
        return await self.dialect.do_all(self, clause, *multiparams, **params)

    async def first(self, clause, *multiparams, **params):
        return await self.dialect.do_first(self, clause,
                                           *multiparams, **params)

    async def scalar(self, clause, *multiparams, **params):
        return await self.dialect.do_scalar(self, clause,
                                            *multiparams, **params)

    async def status(self, clause, *multiparams, **params):
        return await self.dialect.do_status(self, clause,
                                            *multiparams, **params)

    def iterate(self, clause, *multiparams, **params):
        return GinoCursorFactory(lambda: (self, self.metadata), clause,
                                 multiparams, params)
