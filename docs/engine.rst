=====================
Engine and Connection
=====================

**THIS IS A WIP**

:class:`~gino.engine.GinoEngine` is the core of GINO. It acts like a pool of
connections but also does the work of assembling everyone together:

.. image:: engine.png

Under the hood, engine is associated with a specific dialect instance on
creation, e.g. asyncpg dialect. The dialect is actually a set of classes that
implements GINO dialect API, offering all the details about how to operate on
this specific database. In the diagram, gray color means internal, while green
means touchable by end users.

During creation, the engine will also ask the dialect to create a database
connection pool for it. The pool type is also a part of the dialect API,
because asynchronous database drivers usually have their own pool
implementation, thus their GINO dialects should hide such implementation
differences behind the unified diagram API for engine to use.

.. note::

    In SQLAlchemy, database drivers are supposed to follow the DB-API standard,
    which does not usually provide a pool implementation. Therefore, SQLAlchemy
    has its own pool implementation, created directly in engine. This is where
    this diagram doesn't fit SQLAlchemy.

The pool creates raw connections, not the :class:`~gino.engine.GinoConnection`
green in the diagram. The connection in the diagram is a many-to-one wrapper of
the raw connection, because of the reuse and lazy features, we'll get to that
part later. The connection is created by the engine, thus inherits the same
dialect, and is used for running queries.

On the outer side, SQLAlchemy queries can be executed directly on the engine or
connection. When on engine, it will try to acquire a reusable connection to
actually execute the connection, and release the connection after use.

.. note::

    Another difference to SQLAlchemy here: GINO execution methods always return
    final results, while in SQLAlchemy accessing the result may cause further
    implicit database accesses. Therefore GINO engine immediately releases the
    connection when the execution method on the engine returns, but SQLAlchemy
    can only release the connection implicitly when the result data is found
    exhausted.

    By immediately releasing a connection, GINO may not release the related raw
    connection when the raw connection was reused from another parent
    connection. We'll get to this later.

GINO also supports `implicit execution
<https://docs.sqlalchemy.org/en/latest/core/connections.html#connectionless-execution-implicit-execution>`_
without having to specify an engine or connection explicitly. This is done by
binding the engine to the ``db`` instance, also known as the
:class:`~sqlalchemy.schema.MetaData` or the :class:`~gino.api.Gino` instance.
You may possibly bind a :class:`~gino.engine.GinoConnection` instance, but that
is greatly not recommended because it is very much untested.

At last, as the ORM / CRUD feature, models are just add-ons on top of
everything else to generate queries. The parent model class is connected to a
``db`` instance on creation, therefore the models can do implicit execution too
if their ``db`` has a bind.

Then let's get to some details.


Creating Engines
----------------

GINO reuses the strategy system SQLAlchemy provides to create engines. The name
of GINO's strategy to create asynchronous :class:`~gino.engine.GinoEngine` is
just ``gino``, but only available after ``gino`` is imported::

    import gino, sqlalchemy

    async def main():
        e = await sqlalchemy.create_engine('postgresql://...', strategy='gino')
        # e is a GinoEngine

.. tip::

    Please read `this SQLAlchemy document
    <https://docs.sqlalchemy.org/en/latest/core/engines.html#database-urls>`_
    to learn about writing database URLs.

Also the GINO strategy replaces the default driver of dialect ``postgresql://``
from ``psycopg2`` to ``asyncpg``, so that you don't have to replace the URL
as it may be shared between GINO and vanilla SQLAlchemy in parallel.
Alternatively, you can explicitly specify the driver to use by
``postgresql+asyncpg://...`` or just ``asyncpg://...``.

GINO also offers a shortcut as :func:`gino.create_engine`, which only sets the
default strategy to ``gino`` and does nothing more. So here is an identical
example::

    import gino

    async def main():
        e = await gino.create_engine('postgresql://...')
        # e is also a GinoEngine

As you may have noticed, when using the GINO strategy,
:func:`~sqlalchemy.create_engine` returns a coroutine, which must be awaited
for result. Because it will create a database connection pool behind the scene,
and actually making a few initial connections by default.

For it is just SQLAlchemy :func:`~sqlalchemy.create_engine`, the same rules of
parameters apply in GINO too. Well for now, GINO only supports a small amount
of all the parameters listed in SQLAlchemy document (we are working on it!):

For Dialect:

* `isolation_level <https://docs.sqlalchemy.org/en/latest/core/engines.html#sqlalchemy.create_engine.params.isolation_level>`_
* `paramstyle <https://docs.sqlalchemy.org/en/latest/core/engines.html#sqlalchemy.create_engine.params.paramstyle>`_

For Engine:

* `echo <https://docs.sqlalchemy.org/en/latest/core/engines.html#sqlalchemy.create_engine.params.echo>`_
* `execution_options <https://docs.sqlalchemy.org/en/latest/core/engines.html#sqlalchemy.create_engine.params.execution_options>`_
* `logging_name <https://docs.sqlalchemy.org/en/latest/core/engines.html#sqlalchemy.create_engine.params.logging_name>`_

While these parameters are discarded by GINO:

* `module <https://docs.sqlalchemy.org/en/latest/core/engines.html#sqlalchemy.create_engine.params.module>`_

In addition, keyword arguments for creating the underlying pool is accepted
here. In the case of asyncpg, they are from :func:`~asyncpg.pool.create_pool`.
For example, we can create an engine without initial connections::

    e = await gino.create_engine('postgresql://...', min_size=0)

Similar to SQLAlchemy, GINO also provides shortcut to create engine while
setting it as a bind. In SQLAlchemy it is like this::

    import sqlalchemy

    metadata = sqlalchemy.MetaData()
    metadata.bind = 'postgresql://...'

    # or in short

    metadata = sqlalchemy.MetaData('postgresql://...')

This implicitly calls :func:`~sqlalchemy.create_engine` under the hood. However
in GINO, creating an engine requires ``await``, it can no longer be hidden
behind a normal assignment statement. Therefore, GINO removed the assignment
magic in subclass :class:`~gino.api.Gino`, reverted it to simple assignment::

    import gino

    db = gino.Gino()

    async def main():
        # db.bind = 'postgresql://...' doesn't work!! It sets a string on bind
        engine = await gino.create_engine('postgresql://...')
        db.bind = engine

And provided a shortcut to do so::

    engine = await db.set_bind('postgresql://...')

And another simpler shortcut for one-time usage::

    db = await gino.Gino('postgresql://...')

To unset a bind and close the engine::

    engine, db.bind = db.bind, None
    await engine.close()

Or with a shortcut correspondingly::

    await engine.pop_bind().close()

Furthermore, the two steps can be combined into one shortcut with asynchronous
context manager::

    async with db.with_bind('postgresql://...') as engine:
        # your code here

Managing Connections
--------------------

With a :class:`~gino.engine.GinoEngine` at hand, you can acquire connections
from the pool now::

    conn = await engine.acquire()

Don't forget to release it after use::

    await conn.release()

Yes this can be easily missing. The recommended way is to use the asynchronous
context manager::

    async with engine.acquire() as conn:
        # play with the connection

Here ``conn`` is a :class:`~gino.engine.GinoConnection` instance. As mentioned
previously, :class:`~gino.engine.GinoConnection` is mapped to an underlying raw
connection, as shown in following diagram:

.. image:: connection.png

Each column has at most one actual raw connection, and the number is the
sequence the connections are created in this example. It is designed this way
so that GINO could offer two features for connection management: ``reuse`` and
``lazy``. They are keyword arguments on :meth:`~gino.engine.GinoEngine.acquire`
and by default switched off.

reuse
"""""

When acquiring a :class:`~gino.engine.GinoConnection` (2), GINO will borrow a
raw connection (1) from the underlying pool first, and assign it to this
:class:`~gino.engine.GinoConnection` (2). This is the default behavior of
:meth:`~gino.engine.GinoConnection.acquire` with no arguments given. Even when
you are nesting two acquires, you still get two actual raw connection
borrowed::

    async with engine.acquire() as conn1:
        async with engine.acquire() as conn2:
            # conn2 is a completely different connection than conn1

But sometimes ``conn2`` may exist in a different method::

    async def outer():
        async with engine.acquire() as conn1:
            await inner()

    async def inner():
        async with engine.acquire() as conn2:
            # ...

And we probably wish ``inner`` could reuse the same raw connection in
``outer`` to save some resource, or borrow a new one if ``inner`` is
individually called without ``outer``::

    async def outer():
        async with engine.acquire() as conn1:
            await inner(conn1)

    async def inner(conn2=None):
        if conn2 is None:
            async with engine.acquire() as conn2:
                # ...
        else:
            # the same ... again

This is exactly the scenario ``reuse`` could be useful. We can simply tell the
:meth:`~gino.engine.GinoConnection.acquire` to reuse the most recent reusable
connection in current context by setting ``reuse=True``, as presented in this
identical example::

    async def outer():
        async with engine.acquire() as conn1:
            await inner(conn1)

    async def inner():
        async with engine.acquire(reuse=True) as conn2:
            # ...

Back to previous diagram, the blue :class:`~gino.engine.GinoConnection`
instances (3, 4, 6) are "reusing connections" acquired with ``reuse=True``,
while the green ones (2, 5, 7) are not, thus they become "reusable
connections". The green reusable connections are put in a stack in current
context, so that ``acquire(reuse=True)`` always reuses the most recent
connection at the top of the stack. For example, (3) and (4) reuse the only
available (2), therefore (2, 3, 4) all map to the same raw connection (1). Then
after (5), (6) no longer reuses (2) because (5) is now the head of the stack.

.. tip::

    By context, we are actually referring to the context concept in either
    `aiocontextvars <https://github.com/fantix/aiocontextvars>`_ the optional
    dependency or `contextvars
    <https://docs.python.org/3.7/library/contextvars.html>`_ the new module in
    upcoming Python 3.7. Simply speaking, you may treat a function call chain
    including awaited :class:`~asyncio.Task` created in the chain as in the
    same context, something like a thread local in asyncio.

.. note::

    And that is to say, `aiocontextvars
    <https://github.com/fantix/aiocontextvars>`_ is a required dependency for
    ``reuse`` to work correctly in Python 3.6. Without context, the stack is
    always empty for any :meth:`~gino.engine.GinoEngine.acquire` thus no one
    could reuse raw connections at all.

:class:`~gino.engine.GinoConnection` (2) may be created through
``acquire(reuse=True)`` too - because the stack is empty before (2), there is
nothing to reuse, so (2) upgraded itself to a reusable connection.

lazy
""""

As you may have found, :class:`~gino.engine.GinoConnection` (5) does not have
an underlying raw connection, even when it is reused by (6). This is because
both (5) and (6) set ``lazy=True`` on acquire.

A lazy connection will not borrow a raw connection on creation, it will only do
so when have to, e.g. when executing a query or starting a transaction. On
implementation level, ``lazy`` is extremely easy in
:meth:`~gino.engine.GinoEngine.acquire`: if ``lazy=False`` then borrow a raw
connection, else do nothing. That's it. Before executing a query or starting a
transaction, :class:`~gino.egnine.GinoConnection` will always try to borrow a
raw connection if there is none present.

When used together with ``reuse``, at most one raw connection may be borrowed
for one reusing chain. For example, executing queries on both (5) and (6) will
result only one raw connection checked out, no matter which executes first. It
is also worth noting that, if we set ``lazy=False`` on (6), then the raw
connection will be immediately borrowed on acquire, and shared between both (5)
and (6).

reusable
""""""""

Implicit Execution
------------------
