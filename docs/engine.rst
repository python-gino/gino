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
dialect, with which the connection run queries.

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

    By immediately releasing connection, GINO may not release the related raw
    connection, in the case when the releasing connection is reusing raw
    connection of another parent connection. We'll get to this later.

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

Also the GINO strategy replaces the default dialect of ``postgresql://`` from
``psycopg2`` to ``asyncpg``, so that you don't have to replace the URL which
may be shared between GINO and vanilla SQLAlchemy in parallel. GINO also offers
a shortcut as :func:`gino.create_engine`, which only sets the default strategy
to ``gino`` and does nothing more. So here is an identical example::

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


Managing Connections
--------------------


Implicit Execution
------------------
