from __future__ import annotations

from typing import TYPE_CHECKING

from .asyncpg import AsyncpgDialect
from .base import DBAPI
from ..pool.trio import QueuePool

if TYPE_CHECKING:
    from triopg._triopg import TrioConnectionProxy


class TriopgDBAPI(DBAPI):
    def __init__(self):
        import triopg

        async def connect(*args, **kwargs):
            return await triopg.connect(*args, **kwargs).__aenter__()

        self.connect = connect
        self.Error = triopg.PostgresError, triopg.InterfaceError
        self.connection_error_cls = triopg.PostgresConnectionError


class TriopgDialect(AsyncpgDialect):
    poolclass = QueuePool
    supports_server_side_cursors = False

    @classmethod
    def dbapi(cls):
        return TriopgDBAPI()

    async def do_begin(self, dbapi_connection: TrioConnectionProxy):
        rv = dbapi_connection.transaction()
        await rv.__aenter__()
        return rv

    async def do_commit(self, tx):
        await tx.__aexit__(None, None, None)

    async def do_rollback(self, tx):
        await tx.__aexit__(True, None, None)
