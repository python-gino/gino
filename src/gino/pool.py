from sqlalchemy.event import Events


class AsyncPool:
    def __init__(self, creator, dialect):
        self._creator = creator
        self._dialect = dialect

    async def acquire(self):
        return await self._creator()

    async def release(self, conn):
        await self._dialect.disconnect(conn)


class AsyncPoolEvents(Events):
    _target_class_doc = "AsyncPool"
    _dispatch_target = AsyncPool

    def connect(self, dbapi_connection, connection_record):
        pass

    def first_connect(self, dbapi_connection, connection_record):
        pass
