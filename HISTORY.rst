=======
History
=======

GINO 0.6
--------

Migrating to GINO 0.6
^^^^^^^^^^^^^^^^^^^^^

1. Task Local
"""""""""""""

We created a new Python package aiocontextvars_ from previous ``local.py``. If
you made use of the task local features, you should install this package.

Previous ``gino.enable_task_local`` and ``gino.disable_task_local`` are
replaced by :meth:`aiocontextvars.enable_inherit
<aiocontextvars.inherit.enable_inherit>` and
:meth:`aiocontextvars.disable_inherit <aiocontextvars.inherit.disable_inherit>`.
However in GINO 0.5 they controls the whole task local feature switch, while
aiocontextvars_ by default offers task local even without
:meth:`~aiocontextvars.inherit.enable_inherit`, which controls whether the
local storage should be passed between chained tasks. When enabled, it behaves
the same as enabled in 0.5, but you cannot completely turn off the task local
feature while aiocontextvars_ is installed.

There is no ``gino.get_local`` and ``gino.reset_local`` relevant in
aiocontextvars_. The similar thing is :class:`aiocontextvars.ContextVar
<aiocontextvars.var.ContextVar>` instance through its
:meth:`~aiocontextvars.var.ContextVar.get`,
:meth:`~aiocontextvars.var.ContextVar.set` and
:meth:`~aiocontextvars.var.ContextVar.delete` methods.

Previous ``gino.is_local_root`` is now :attr:`not
aiocontextvars.Context.current().inherited
<aiocontextvars.context.Context.inherited>`.

2. GinoEngine
"""""""""""""

GINO 0.6 hides :class:`asyncpg.Pool <asyncpg.pool.Pool>` behind the new
SQLAlchemy-alike :class:`gino.GinoEngine <gino.engine.GinoEngine>`. Instead of
doing this in 0.5::

    async with db.create_pool('postgresql://...') as pool:
        # your code here

You should change it to this in 0.6::

    async with db.with_bind('postgresql://...') as engine:
        # your code here

This equals to::

    engine = await gino.create_engine('postgresql://...')
    db.bind = engine
    try:
        # your code here
    finally:
        db.bind = None
        await engine.close()

Or::

    engine = await db.set_bind('postgresql://...')
    try:
        # your code here
    finally:
        await db.pop_bind().close()

Or even this::

    db = await gino.Gino('postgresql://...')
    try:
        # your code here
    finally:
        await db.pop_bind().close()

Choose whichever suits you the best.

Obviously :class:`~gino.engine.GinoEngine` doesn't provide :class:`asyncpg.Pool
<asyncpg.pool.Pool>` methods directly any longer, but you can get the
underlying :class:`asyncpg.Pool <asyncpg.pool.Pool>` object through
:attr:`engine.raw_pool <gino.engine.GinoEngine.raw_pool>` property.

``GinoPool.get_current_connection`` is now changed to
:attr:`~gino.engine.GinoEngine.current_connection` property on
:class:`~gino.engine.GinoEngine` instances to support multiple engines.

``GinoPool().execution_option`` is gone, instead
:meth:`~gino.engine.GinoEngine.update_execution_options` on
:class:`~gino.engine.GinoEngine` instance is available.

``GinoPool().metadata`` is gone, :attr:`~gino.engine.GinoEngine.dialect` is
still available.

These methods exist both in 0.5 ``GinoPool`` and 0.6
:class:`~gino.engine.GinoEngine`:
:meth:`~gino.engine.GinoEngine.close`,
:meth:`~gino.engine.GinoEngine.acquire`,
:meth:`~gino.engine.GinoEngine.release`,
:meth:`~gino.engine.GinoEngine.all`,
:meth:`~gino.engine.GinoEngine.first`,
:meth:`~gino.engine.GinoEngine.scalar`,
:meth:`~gino.engine.GinoEngine.status`.

3. GinoConnection
"""""""""""""""""

Similarly, :class:`~gino.engine.GinoConnection` in 0.6 is no longer a subclass
of :class:`asyncpg.Connection <asyncpg.connection.Connection>`, instead it has
a :class:`asyncpg.Connection <asyncpg.connection.Connection>` instance,
accessible through :attr:`GinoConnection().raw_connection
<gino.engine.GinoConnection.raw_connection>` property.

``GinoConnection().metadata`` is deleted in 0.6, while
:attr:`gino.engine.GinoConnection.dialect` remained.

:meth:`GinoConnection().execution_options
<gino.engine.GinoConnection.execution_options>` is changed from a mutable dict
in 0.5 to a method returning a copy of current connection with the new options,
the same as SQLAlchemy behavior.

And :meth:`~gino.engine.GinoConnection.all`,
:meth:`~gino.engine.GinoConnection.first`,
:meth:`~gino.engine.GinoConnection.scalar`,
:meth:`~gino.engine.GinoConnection.status`,
:meth:`~gino.engine.GinoConnection.iterate`,
:meth:`~gino.engine.GinoConnection.transaction` remained in 0.6.

4. Query API
""""""""""""

All five query APIs :meth:`~gino.api.GinoExecutor.all`,
:meth:`~gino.api.GinoExecutor.first`,
:meth:`~gino.api.GinoExecutor.scalar`,
:meth:`~gino.api.GinoExecutor.status`,
:meth:`~gino.api.GinoExecutor.iterate` now accept the same parameters
as SQLAlchemy :meth:`~sqlalchemy.engine.Connectable.execute`, meaning they
accept raw SQL text, or multiple sets of parameters for "executemany". Please
note, if the parameters are recognized as "executemany", none of the methods
will return anything. Meanwhile, they no longer accept the parameter ``bind``
if they did. Just use the API on the :class:`~gino.engine.GinoEngine` or
:class:`~gino.engine.GinoConnection` object instead.

5. Transaction
""""""""""""""

Transaction interface is rewritten. Now in 0.6, a
:class:`~gino.transaction.GinoTransaction` object is provided consistently from
all 3 methods::

    async with db.transaction() as tx:
        # within transaction

    async with engine.transaction() as tx:
        # within transaction

    async with engine.acquire() as conn:
        async with conn.transaction() as tx:
            # within transaction

And different usage with ``await``::

    tx = await db.transaction()
    try:
        # within transaction
        await tx.commit()
    except:
        await tx.rollback()
        raise

The :class:`~gino.engine.GinoConnection` object is available at
:attr:`tx.connection <gino.transaction.GinoTransaction.connection>`, while
underlying transaction object from database driver is available at
:attr:`tx.raw_transaction <gino.transaction.GinoTransaction.raw_transaction>` -
for asyncpg it is an :class:`asyncpg.transaction.Transaction` object.

0.6.0 (TBD)
^^^^^^^^^^^^^^^^^^

This is also version 1.0 beta 2.

* [Breaking] API Refactored, ``Pool`` replaced with ``Engine``

  * New API ``Engine`` replaced asyncpg ``Pool`` (#59)
  * Supported different dialects, theoretically
  * Used aiocontextvars_ instead of builtin task local (#89)
* [Breaking] Fixed query API with ``multiparams`` (executemany) to return correctly (#20)
* [Breaking] The query methods no longer accept the parameter ``bind``
* [Breaking] ``Gino`` no longer exposes ``postgresql`` types
* Added ``echo`` on engine (#142)
* Added tests to cover 80% of code
* Added ``gino`` extension on ``SchemaItem`` for ``create_all`` and so on (#76 #106)
* Added ``gino`` on model classes for ``create`` or ``drop``
* Added ``_update_request_cls`` on ``CRUDModel`` (#147)
* Rewrote the documentation (#146)

.. _aiocontextvars: https://github.com/fantix/aiocontextvars


GINO 0.5
--------

0.5.8 (2018-02-14)
^^^^^^^^^^^^^^^^^^

* Preparing for 0.6.0 which will be a breaking release
* Fixed wrong value of ``Enum`` in creation (Contributed by Sergey Kovalev in #126)

0.5.7 (2017-11-24)
^^^^^^^^^^^^^^^^^^

This is an emergency fix for 0.5.6.

* Fixed broken lazy connection (Contributed by Ádám Barancsuk in #114)
* Added ``Model.outerjoin``

0.5.6 (2017-11-23)
^^^^^^^^^^^^^^^^^^

* Changed to use unnamed statement when possible (#80 #90)
* Added more example (Contributed by Kentoseth in #109)
* Added ``Model.join`` and made ``Model`` selectable (Contributed by Ádám Barancsuk in #112 #113)

0.5.5 (2017-10-18)
^^^^^^^^^^^^^^^^^^

* Ensured clean connection if transaction acquire fails (Contributed by Vladimir Goncharov in #87)
* Added ability to reset local storage (#84)
* Fixed bug in JSON property update
* Added update chaining feature

0.5.4 (2017-10-04)
^^^^^^^^^^^^^^^^^^

* Updated example (Contributed by Kinware in #75)
* Added ``Model.insert`` (Contributed by Neal Wang in #63)
* Fixed issue that non-lazy acquiring fails dirty (#79)

0.5.3 (2017-09-23)
^^^^^^^^^^^^^^^^^^

* Fixed ``no module named cutils`` error (Contributed by Vladimir Goncharov in #73)

0.5.2 (2017-09-10)
^^^^^^^^^^^^^^^^^^

* Added missing driver name on dialect (#67)
* Fixed dialect to support native decimal type (#67)

0.5.1 (2017-09-09)
^^^^^^^^^^^^^^^^^^

This is an emergency fix for 0.5.0.

* Reverted the extension, back to pure Python (#60)
* Used SQLAlchemy ``RowProxy``
* Added ``first_or_404``
* Fixed bug that ``GinoPool`` cannot be inherited

0.5.0 (2017-09-03)
^^^^^^^^^^^^^^^^^^

This is also version 1.0 beta 1.

* [Breaking] Internal refactor: extracted and isolated a few modules, partially rewritten

  * Extracted CRUD operations
  * Core operations are moved to ``dialect`` and execution context
  * Removed ``guess_model``, switched to explicit execution options
  * Turned ``timeout`` parameter to an execution option
  * Extracted ``pool``, ``connection`` and ``api`` from ``asyncpg_delegate``
* Added support for SQLAlchemy execution options, and a few custom options
* [Breaking] Made `Model.select` return rows by default (#39)
* Moved `get_or_404` to extensions (#38)
* Added iterator on model classes (#43)
* Added Tornado extension (Contributed by Vladimir Goncharov)
* Added `Model.to_dict` (#47)
* Added an extension module to update `asyncpg.Record` with processed results


Early Development Releases
--------------------------

0.4.1 (2017-08-20)
^^^^^^^^^^^^^^^^^^

* Support ``select`` on model instance

0.4.0 (2017-08-15)
^^^^^^^^^^^^^^^^^^

* Made ``get_or_404`` more friendly when Sanic is missing (Contributed by Neal Wang in #23 #31)
* Delegated ``sqlalchemy.__all__`` (Contributed by Neal Wang in #10 #33)
* [Breaking] Rewrote JSON/JSONB support (#29)
* Added ``lazy`` parameter on ``db.acquire`` (Contributed by Binghan Li in #32)
* Added Sanic integration (Contributed by Binghan Li, Tony Wang in #30 #32 #34)
* Fixed ``iterate`` API to be compatible with asyncpg (#32)
* Unified exceptions
* [Breaking] Changed ``update`` API (#29)
* Bug fixes

0.3.0 (2017-08-07)
^^^^^^^^^^^^^^^^^^

* Supported ``__table_args__`` (#12)
* Introduced task local to manage connection in context (#19)
* Added ``query.gino`` extension for in-place execution
* Refreshed README (#3)
* Adopted PEP 487 (Contributed by Tony Wang in #17 #27)
* Used ``weakref`` on ``__model__`` of table and query (Contributed by Tony Wang)
* Delegated asyncpg ``timeout`` parameter (Contributed by Neal Wang in #16 #22)

0.2.3 (2017-08-04)
^^^^^^^^^^^^^^^^^^

* Supported any primary key (Contributed by Tony Wang in #11)

0.2.2 (2017-08-02)
^^^^^^^^^^^^^^^^^^

* Supported SQLAlchemy result processor
* Added rich support on JSON/JSONB
* Bug fixes

0.2.1 (2017-07-28)
^^^^^^^^^^^^^^^^^^

* Added ``update`` and ``delete`` API

0.2.0 (2017-07-28)
^^^^^^^^^^^^^^^^^^

* Changed API, no longer reuses asyncpg API

0.1.1 (2017-07-25)
^^^^^^^^^^^^^^^^^^

* Added ``db.bind``
* API changed: parameter ``conn`` renamed to optional ``bind``
* Delegated asyncpg Pool with ``db.create_pool``
* Internal enhancement and bug fixes

0.1.0 (2017-07-21)
^^^^^^^^^^^^^^^^^^

* First release on PyPI.
