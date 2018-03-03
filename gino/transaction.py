class _Break(Exception):
    def __init__(self, tx, commit):
        super().__init__()
        self.tx = tx
        self.commit = commit


class GinoTransaction:
    def __init__(self, conn, args, kwargs):
        self._conn = conn
        self._args = args
        self._kwargs = kwargs
        self._tx = None
        self._managed = None

    async def _begin(self):
        raw_conn = await self._conn.get_raw_connection()
        self._tx = self._conn.dialect.transaction(raw_conn,
                                                  self._args, self._kwargs)
        await self._tx.begin()
        return self

    @property
    def connection(self):
        return self._conn

    @property
    def raw_transaction(self):
        return self._tx.raw_transaction

    def raise_commit(self):
        raise _Break(self, True)

    async def commit(self):
        if self._managed:
            self.raise_commit()
        else:
            await self._tx.commit()

    def raise_rollback(self):
        raise _Break(self, False)

    async def rollback(self):
        if self._managed:
            self.raise_rollback()
        else:
            await self._tx.rollback()

    def __await__(self):
        assert self._managed is None
        self._managed = False
        return self._begin().__await__()

    async def __aenter__(self):
        assert self._managed is None
        self._managed = True
        await self._begin()
        return self

    async def __aexit__(self, ex_type, ex, ex_tb):
        try:
            is_break = ex_type is _Break
            if is_break and ex.commit:
                ex_type = None
            if ex_type is None:
                await self._tx.commit()
            else:
                await self._tx.rollback()
        except Exception:
            await self._tx.rollback()
            raise
        if is_break and ex.tx is self:
            return True
