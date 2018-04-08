===========
Transaction
===========

It is crucial to correctly manage transactions in an asynchronous program,
because you never know how much time an ``await`` will actually wait for, it
will cause disasters if transactions are on hold for too long. GINO enforces
explicit transaction management to help dealing with it.


Basic usage
-----------

Transactions belong to :class:`~gino.engine.GinoConnection`. The most common
way to use transactions is through an ``async with`` statement::

    async with connection.transaction() as tx:
        await connection.status('INSERT INTO mytable VALUES(1, 2, 3)')

This guarantees a transaction is opened when entering the ``async with`` block,
and closed when exiting the block - committed if exits normally, or rolled back
by exception. The underlying transaction instance from the database driver is
available at :attr:`~gino.transaction.GinoTransaction.raw_transaction`, but in
most cases you don't need to touch it.

GINO provides two convenient shortcuts to end the transaction early:

* :meth:`tx.raise_commit() <gino.transaction.GinoTransaction.raise_commit>`
* :meth:`tx.raise_rollback() <gino.transaction.GinoTransaction.raise_rollback>`

They will raise an internal exception to correspondingly commit or rollback the
transaction, thus the code within the ``async with`` block after
:meth:`~gino.transaction.GinoTransaction.raise_commit` or
:meth:`~gino.transaction.GinoTransaction.raise_rollback` is skipped. The
internal exception is inherited from :exc:`BaseException` so that normal ``try
... except Exception`` block can't trap it. This exception stops propagating at
the end of ``async with`` block, so you don't need to worry about handling it.

Transactions can also be started on a :class:`~gino.engine.GinoEngine`::

    async with engine.transaction() as tx:
        await engine.status('INSERT INTO mytable VALUES(1, 2, 3)')

Here a :class:`~gino.engine.GinoConnection` is borrowed implicitly before
entering the transaction, and guaranteed to be returned after transaction is
done. The :class:`~gino.engine.GinoConnection` instance is accessible at
:attr:`tx.connection <gino.transaction.GinoTransaction.connection>`. Other than
that, everything else is the same.

.. important::

    The implicit connection is by default borrowed with ``reuse=True``. That
    means using :meth:`~gino.engine.GinoEngine.transaction` of
    :class:`~gino.engine.GinoEngine` within a connection context is the same as
    calling :meth:`~gino.engine.GinoConnection.transaction` of the current
    connection without having to reference it, no separate connection shall be
    created.

Similarly, if your :class:`~gino.api.Gino` instance has a bind, you may also do
the same on it::

    async with db.transaction() as tx:
        await db.status('INSERT INTO mytable VALUES(1, 2, 3)')


Nested Transactions
-------------------

Transactions can be nested, nested transaction will create a `savepoint
<https://www.postgresql.org/docs/current/static/sql-savepoint.html>`_ as for
now on asyncpg. A similar example from asyncpg doc::

    async with connection.transaction() as tx1:
        await connection.status('CREATE TABLE mytab (a int)')

        # Create a nested transaction:
        async with connection.transaction() as tx2:
            await connection.status('INSERT INTO mytab (a) VALUES (1), (2)')
            # Rollback the nested transaction:
            tx2.raise_rollback()

        # Because the nested transaction was rolled back, there
        # will be nothing in `mytab`.
        assert await connection.all('SELECT a FROM mytab') == []

As you can see, the :meth:`~gino.transaction.GinoTransaction.raise_rollback`
breaks only the ``async with`` block of the specified ``tx2``, the outer
transaction ``tx1`` just continued. What if we break the outer transaction from
within the inner transaction? The inner transaction context won't trap the
internal exception because it recognizes the exception is not created upon
itself. Instead, the inner transaction context only follows the behavior to
either commit or rollback, and lets the exception propagate.

Because of the default reusing behavior, transactions on engine or ``db``
follows the same nesting rules. Please see
:class:`~gino.transactions.GinoTransaction` for more information.


Manual Control
--------------

Other than using ``async with``, you can also manually control the
transaction::

    tx = await db.transaction()
    try:
        await db.status('INSERT INTO mytable VALUES(1, 2, 3)')
        await tx.commit()
    except Exception:
        await tx.rollback()
        raise

You can't use :meth:`~gino.transaction.GinoTransaction.raise_commit` or
:meth:`~gino.transaction.GinoTransaction.raise_rollback` here, similarly it is
prohibited to use :meth:`~gino.transaction.GinoTransaction.commit` and
:meth:`~gino.transaction.GinoTransaction.rollback` in an ``async with`` block.
