=======
History
=======

GINO 0.8
--------

This is also version 1.0 release candidate.

Migrating to GINO 0.8
^^^^^^^^^^^^^^^^^^^^^

1. contextvars
""""""""""""""

We introduced aiocontextvars_ 0.2.0 which is revamped to be compatible with
PEP-567 without manual interference by a few simple implicit patches. To
upgrade to GINO 0.8, please remove the ``enable_inherit()`` or
``disable_inherit()`` calls, because they are the default behavior now thus
no longer exist. However, you'll need to confirm that the event loop in use is
always created **after** importing ``gino`` or ``aiocontextvars``, or the patch
won't work correctly.

There is nothing to worry about in Python 3.7.

2. none_as_none
"""""""""""""""

When GINO tries to load a row with all ``NULL`` values into an instance, it
will now by default return ``None`` instead of an instance with all ``None``
attributes. To recover the default behavior of 0.7, please specify
``none_as_none(False)`` in affected model loader.

This is especially applicable to relationship sub-loaders - if the sub-loader
found it all ``NULL``, no instance will be set to parent instance. For
example::

    child = await Child.load(parent=Parent).query.gino.first()

If ``child.parent_id`` is ``NULL`` in database, then the ``child`` instance
won't be called with any ``setattr(child, 'parent', ...)`` at all. (If you need
``child.parent == None`` in this case, consider setting default value
``parent = None`` in child model.)

Please note, it is deprecated to disable ``none_as_none``, and disabling will
be removed in GINO 1.0.

0.8.3 (UNRELEASED)
^^^^^^^^^^^^^^^^^^

* Customizable db attribute name in aiohttp app instance (#457)

0.8.2 (2019-03-07)
^^^^^^^^^^^^^^^^^^

* Added exception for unknown JSON properties (#406 #408)
* Supported Quart 0.7 (#411)
* Accepted kwargs for db init in extensions (#407 #427)
* Added custom config parameter to aiohttp middleware (Contributed by Michał Dziewulski in #440)
* Added NullPool (#437 #441)
* Unpinned dependency versions (#447)
* Added support for SQLAlchemy 1.3 (#433 #451)

0.8.1 (2018-12-08)
^^^^^^^^^^^^^^^^^^

* Alias supported ``Label`` (#365)
* Docs update (#308, 4c59ad, #401 by Pascal van Kooten)
* Version requirement for SQLAlchemy is updated to ``>=1.2`` (#378 #382)
* Added option for SSL in aiohttp extension (Contributed by Martin Zaťko in #387 #393)
  * And all other extensions (#395)
* Supported Tornado 5 (#396, also thanks to Vladimir Goncharov)
* Fixed custom JSON/JSONB type support (#402 #403)

(Most fixes done by Tony Wang)

0.8.0 (2018-10-16)
^^^^^^^^^^^^^^^^^^

* Welcome Tony Wang to the maintenance team (#335)
* Allowed custom column names (#261 #297)
* Allowed column instance in ``model.load()`` (Contributed by Jekel in #323)
* [Breaking] Upgraded to aiocontextvars 0.2.0 (#333)
* Fixed bug that the same empty stack is shared between sub-tasks (#313 #334)
* [Breaking] Made ``none_as_none()`` the default behavior (#351)
* Bug fixes and docs update


GINO 0.7
--------

This is also version 1.0 beta 3.

0.7.7 (2018-12-08)
^^^^^^^^^^^^^^^^^^

* Backported fix for custom JSON/JSONB type support (#402 #403)

0.7.6 (2018-08-26)
^^^^^^^^^^^^^^^^^^

* Updated library support (Contributed by Tony Wang in #275 #309)
* Added ``none_as_none()`` (#281 #282)
* Added ``ARRAY`` alias in asyncpg dialect module (Contributed by Mykyta Holubakha in #289)
* Added ``Model.lookup()`` to prevent updating whole table without primary key (#287 #288)
* Added ``DB_ECHO`` in extension options (Contributed by Mykyta Holubakha in #298)
* Fixed broken JSON/JSONB result processor since 0.5.8 (Contributed by Tony Wang in #291 #305)
* Removed bad rollback after a failing commit (Contributed by Tony Wang in #302 #304)
* Fixed to raise ``UninitializedError`` if bind is ``None`` (Contributed by Tony Wang in #307 #310)

0.7.5 (2018-07-26)
^^^^^^^^^^^^^^^^^^

* Added friendly error message when using abstract models by mistake (#224)
* Supported Python 3.7 (Contributed by Tony Wang in #265)
* Updated documentation
* Fixed a bug in TupleLoader (Contributed by Pavol Vargovcik in #279 #280)

0.7.4 (2018-06-10)
^^^^^^^^^^^^^^^^^^

* Added aiocontextvars as required dependency required for Python 3.5 and 3.6 (#228)
* Added Quart support (#213)
* Fixed Tornado options parsing (#231)
* Improved coding style and test coverage

0.7.3 (2018-05-19)
^^^^^^^^^^^^^^^^^^

* Fix for failing binary type (#225)

0.7.2 (2018-05-15)
^^^^^^^^^^^^^^^^^^

* Added prepared statement support (#14)
* Added dsn in extension config (Contributed by Yurii Shtrikker in #215)

0.7.1 (2018-05-03)
^^^^^^^^^^^^^^^^^^

* Added support for inline model constraints (Contributed by Kinware in #198)
* Added docs and tests for using SSL (#202)
* Added ``declared_attr`` (#204)
* Allowed ``ModelLoader`` passively load partial model (#216)

0.7.0 (2018-04-18)
^^^^^^^^^^^^^^^^^^

* Added Python 3.5 support (#187)
* Added support to use ``dict`` as ident for ``Model.get`` (#192)
* Added result loader (partial relationship support) (#13)
* Added documentation on relationship and transaction (#146)


GINO 0.6
--------

This is also version 1.0 beta 2.

Migrating to GINO 0.6
^^^^^^^^^^^^^^^^^^^^^

1. Task Local
"""""""""""""

We created a new Python package aiocontextvars_ from previous ``local.py``. If
you made use of the task local features, you should install this package.

Previous ``gino.enable_task_local()`` and ``gino.disable_task_local()`` are
replaced by ``aiocontextvars.enable_inherit()`` and
``aiocontextvars.disable_inherit()``. However in GINO 0.5 they controls the
whole task local feature switch, while aiocontextvars_ by default offers task
local even without ``enable_inherit()``, which controls whether the local
storage should be passed between chained tasks. When enabled, it behaves the
same as enabled in 0.5, but you cannot completely turn off the task local
feature while aiocontextvars_ is installed.

There is no ``gino.get_local()`` and ``gino.reset_local()`` relevant in
aiocontextvars_. The similar thing is ``aiocontextvars.ContextVar`` instance
through its ``get()``, ``set()`` and ``delete()`` methods.

Previous ``gino.is_local_root()`` is now
``not aiocontextvars.Context.current().inherited``.

2. Engine
"""""""""

GINO 0.6 hides ``asyncpg.Pool`` behind the new SQLAlchemy-alike
``gino.GinoEngine``. Instead of doing this in 0.5::

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

Obviously ``GinoEngine`` doesn't provide ``asyncpg.Pool`` methods directly any
longer, but you can get the underlying ``asyncpg.Pool`` object through
``engine.raw_pool`` property.

``GinoPool.get_current_connection()`` is now changed to ``current_connection``
property on ``GinoEngine`` instances to support multiple engines.

``GinoPool.execution_option`` is gone, instead ``update_execution_options()``
on ``GinoEngine`` instance is available.

``GinoPool().metadata`` is gone, ``dialect`` is still available.

``GinoPool.release()`` is removed in ``GinoEngine`` and ``Gino``, the
``release()`` method on ``GinoConnection`` object should be used instead.

These methods exist both in 0.5 ``GinoPool`` and 0.6 ``GinoEngine``:
``close()``, ``acquire()``, ``all()``, ``first()``, ``scalar()``, ``status()``.

3. GinoConnection
"""""""""""""""""

Similarly, ``GinoConnection`` in 0.6 is no longer a subclass of
``asyncpg.Connection``, instead it has a ``asyncpg.Connection`` instance,
accessable through ``GinoConnection.raw_connection`` property.

``GinoConnection.metadata`` is deleted in 0.6, while ``dialect`` remained.

``GinoConnection.execution_options()`` is changed from a mutable dict in 0.5 to
a method returning a copy of current connection with the new options, the same
as SQLAlchemy behavior.

``GinoConnection.release()`` is still present, but its default behavior has
been changed to permanently release this connection. You should add argument
``permanent=False`` to remain its previous behavior.

And ``all()``, ``first()``, ``scalar()``, ``status()``, ``iterate()``,
``transaction()`` remained in 0.6.

4. Query API
""""""""""""

All five query APIs ``all()``, ``first()``, ``scalar()``, ``status()``,
``iterate()`` now accept the same parameters as SQLAlchemy ``execute()``,
meaning they accept raw SQL text, or multiple sets of parameters for
"executemany". Please note, if the parameters are recognized as "executemany",
none of the methods will return anything. Meanwhile, they no longer accept the
parameter ``bind`` if they did. Just use the API on the ``GinoEngine`` or
``GinoConnection`` object instead.

5. Transaction
""""""""""""""

Transaction interface is rewritten. Now in 0.6, a ``GinoTransaction`` object is
provided consistently from all 3 methods::

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

The ``GinoConnection`` object is available at ``tx.connection``, while
underlying transaction object from database driver is available at
``tx.transaction`` - for asyncpg it is an ``asyncpg.transaction.Transaction``
object.

0.6.6 (2018-05-18)
^^^^^^^^^^^^^^^^^^

* Backported a fix for failing binary type (#225)

0.6.5 (2018-04-18)
^^^^^^^^^^^^^^^^^^

* Abandoned 0.6.4 and keep 0.6.x stable
* Backported doc for transaction

0.6.4 (2018-04-16)
^^^^^^^^^^^^^^^^^^

Abandoned version, please use 0.7.0 instead.

0.6.3 (2018-04-08)
^^^^^^^^^^^^^^^^^^

* Added aiohttp support
* Added support for calling ``create()`` on model instances (Contributed by Kinware in #178 #180)
* Fixed ``get()`` by string, and misc environment issues (Contributed by Tony Wang in #191 193 #183 #184)

0.6.2 (2018-03-24)
^^^^^^^^^^^^^^^^^^

* Fixed SQLAlchemy prefetch issue (#141)
* Fixed issue that mixin class on Model not working (#174)
* Added more documentation (Thanks Olaf Conradi for reviewing)

0.6.1 (2018-03-18)
^^^^^^^^^^^^^^^^^^

* Fixed ``create`` and ``drop`` for ``Enum`` type (#160)
* A bit more documentation (#159)

0.6.0 (2018-03-14)
^^^^^^^^^^^^^^^^^^

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
* Added ``gino`` extension on model classes for ``create()`` or ``drop()``
* Added ``_update_request_cls`` on ``CRUDModel`` (#147)
* Rewrote the documentation (#146)

.. _aiocontextvars: https://github.com/fantix/aiocontextvars


GINO 0.5
--------

This is also version 1.0 beta 1.

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

Considered as alpha releases.


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
