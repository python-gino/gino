from __future__ import annotations

import typing

from sqlalchemy.engine import Transaction
from sqlalchemy.ext.asyncio.base import StartableContext
from sqlalchemy.util import greenlet_spawn

if typing.TYPE_CHECKING:
    from .engine import GinoConnection


class _Break(BaseException):
    def __init__(self, tx, commit):
        super().__init__()
        self.tx = tx
        self.commit = commit


class GinoTransaction(StartableContext):
    """
    Represents an underlying database transaction and its connection, offering
    methods to manage this transaction.

    :class:`.GinoTransaction` is supposed to be created by either
    :meth:`gino.engine.GinoConnection.transaction`, or
    :meth:`gino.engine.GinoEngine.transaction`, or
    :meth:`gino.api.Gino.transaction`, shown as follows::

        async with db.transaction() as tx:
            ...

        async with engine.transaction() as tx:
            ...

        async with conn.transaction() as tx:
            ...

        tx = await conn.transaction()
        try:
            ...
            await tx.commit()
        except Exception:
            await tx.rollback()
            raise

    When in use with asynchronous context manager, :class:`.GinoTransaction`
    will be in **managed** mode, while the last example with ``await`` will put
    the :class:`.GinoTransaction` in **manual** mode where you have to call
    the :meth:`.commit` or :meth:`.rollback` to manually close the transaction.

    In **managed** mode the transaction will be automatically committed or
    rolled back on exiting the ``async with`` block depending on whether there
    is an exception or not. Meanwhile, you can explicitly exit the transaction
    early by :meth:`.raise_commit` or :meth:`.raise_rollback` which will raise
    an internal exception managed by the asynchronous context manager and
    interpreted as a commit or rollback action. In a nested transaction
    situation, the two exit-early methods always close up the very transaction
    which the two methods are referenced upon - all children transactions are
    either committed or rolled back correspondingly, while no parent
    transaction was ever touched. For example::

        async with db.transaction() as tx1:
            async with db.transaction() as tx2:
                async with db.transaction() as tx3:
                    tx2.raise_rollback()
                    # Won't reach here
                # Won't reach here
            # Continues here with tx1, with both tx2 and tx3 rolled back.

            # For PostgreSQL, tx1 can still be committed successfully because
            # tx2 and tx3 are just SAVEPOINTs in transaction tx1

    .. tip::

        The internal exception raised from :meth:`.raise_commit` and
        :meth:`.raise_rollback` is a subclass of :exc:`BaseException`, so
        normal ``try ... except Exception:`` can't trap the commit or rollback.

    """

    __slots__ = ("_connection", "_sync_transaction", "_nested", "_managed", "_kwargs")

    def __init__(self, connection: GinoConnection, **kwargs):
        self._connection = connection
        self._sync_transaction: typing.Optional[Transaction] = None
        self._managed = None
        self._kwargs = kwargs

    @property
    def connection(self):
        return self._connection

    async def start(self):
        assert self._sync_transaction is None, "cannot start the same transaction twice"
        conn = await self._connection.acquire()
        in_trans = conn.in_transaction()
        if not in_trans:
            options = {}
            isolation = self._kwargs.get("isolation")
            if isolation:
                options["isolation_level"] = isolation.upper()
            else:
                options["isolation_level"] = (
                    conn.dialect.isolation_level or conn.dialect.default_isolation_level
                )
            if isolation == "SERIALIZABLE":
                if self._kwargs.get("readonly"):
                    options["postgresql_readonly"] = True
                if self._kwargs.get("deferrable"):
                    options["postgresql_deferrable"] = True
            conn = conn.execution_options(**options)

        self._sync_transaction = await greenlet_spawn(
            conn.begin_nested if in_trans else conn.begin
        )
        if not in_trans:
            if conn.dialect.driver == "asyncpg":
                await conn.connection.connection._start_transaction()
        return self

    async def _commit(self):
        if self._sync_transaction is None:
            self._raise_for_not_started()
        await greenlet_spawn(self._sync_transaction.commit)
        await self._reset()

    async def _rollback(self):
        if self._sync_transaction is None:
            self._raise_for_not_started()
        await greenlet_spawn(self._sync_transaction.rollback)
        await self._reset()

    async def _reset(self):
        conn = self._sync_transaction.connection
        if (
            not conn.in_transaction()
            and conn.get_execution_options().get("isolation_level", "AUTOCOMMIT")
            != "AUTOCOMMIT"
        ):
            await greenlet_spawn(
                conn.execution_options,
                isolation_level="AUTOCOMMIT",
                postgresql_readonly=False,
                postgresql_deferrable=False,
            )

    def raise_commit(self):
        """
        Only available in managed mode: skip rest of the code in this
        transaction and commit immediately by raising an internal exception,
        which will be caught and handled by the asynchronous context manager::

            async with db.transaction() as tx:
                await user.update(age=64).apply()
                tx.raise_commit()
                await user.update(age=32).apply()  # won't reach here

            assert user.age == 64  # no exception raised before

        """
        if not self._managed:
            raise AssertionError("Illegal in manual mode, use `commit` instead.")
        raise _Break(self, True)

    async def commit(self):
        """
        Only available in manual mode: manually commit this transaction.

        """
        if self._managed:
            raise AssertionError(
                "Illegal in managed mode, " "use `raise_commit` instead."
            )
        await self._commit()

    def raise_rollback(self):
        """
        Only available in managed mode: skip rest of the code in this
        transaction and rollback immediately by raising an internal exception,
        which will be caught and handled by the asynchronous context manager::

            assert user.age == 64  # assumption

            async with db.transaction() as tx:
                await user.update(age=32).apply()
                tx.raise_rollback()
                await user.update(age=128).apply()  # won't reach here

            assert user.age == 64  # no exception raised before

        """
        if not self._managed:
            raise AssertionError("Illegal in manual mode, use `rollback` instead.")
        raise _Break(self, False)

    async def rollback(self):
        """
        Only available in manual mode: manually rollback this transaction.

        """
        if self._managed:
            raise AssertionError(
                "Illegal in managed mode, " "use `raise_rollback` instead."
            )
        await self._rollback()

    def __await__(self):
        if self._managed is not None:
            raise AssertionError("Cannot start the same transaction twice")
        self._managed = False
        return super().__await__()

    async def __aenter__(self):
        if self._managed is not None:
            raise AssertionError("Cannot start the same transaction twice")
        self._managed = True
        return await super().__aenter__()

    async def __aexit__(self, ex_type, ex, ex_tb):
        is_break = ex_type is _Break
        if is_break and ex.commit or ex_type is None:
            await self._commit()
        else:
            await self._rollback()
        if is_break and ex.tx is self:
            return True
