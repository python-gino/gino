=======
History
=======

0.5.8 (2018-02-14)
------------------

* Preparing for 0.6.0 which will be a breaking release
* Fixed wrong value of ``Enum`` in creation (Contributed by Sergey Kovalev in #126)

0.5.7 (2017-11-24)
------------------

This is an emergency fix for 0.5.6.

* Fixed broken lazy connection (Contributed by Ádám Barancsuk in #114)
* Added ``Model.outerjoin``

0.5.6 (2017-11-23)
------------------

* Changed to use unnamed statement when possible (#80 #90)
* Added more example (Contributed by Kentoseth in #109)
* Added ``Model.join`` and made ``Model`` selectable (Contributed by Ádám Barancsuk in #112 #113)

0.5.5 (2017-10-18)
------------------

* Ensured clean connection if transaction acquire fails (Contributed by Vladimir Goncharov in #87)
* Added ability to reset local storage (#84)
* Fixed bug in JSON property update
* Added update chaining feature

0.5.4 (2017-10-04)
------------------

* Updated example (Contributed by Kinware in #75)
* Added ``Model.insert`` (Contributed by Neal Wang in #63)
* Fixed issue that non-lazy acquiring fails dirty (#79)

0.5.3 (2017-09-23)
------------------

* Fixed ``no module named cutils`` error (Contributed by Vladimir Goncharov in #73)

0.5.2 (2017-09-10)
------------------

* Added missing driver name on dialect (#67)
* Fixed dialect to support native decimal type (#67)

0.5.1 (2017-09-09)
------------------

This is an emergency fix for 0.5.0.

* Reverted the extension, back to pure Python (#60)
* Used SQLAlchemy ``RowProxy``
* Added ``first_or_404``
* Fixed bug that ``GinoPool`` cannot be inherited

0.5.0 (2017-09-03)
------------------

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

0.4.1 (2017-08-20)
------------------

* Support ``select`` on model instance

0.4.0 (2017-08-15)
------------------

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
------------------

* Supported ``__table_args__`` (#12)
* Introduced task local to manage connection in context (#19)
* Added ``query.gino`` extension for in-place execution
* Refreshed README (#3)
* Adopted PEP 487 (Contributed by Tony Wang in #17 #27)
* Used ``weakref`` on ``__model__`` of table and query (Contributed by Tony Wang)
* Delegated asyncpg ``timeout`` parameter (Contributed by Neal Wang in #16 #22)

0.2.3 (2017-08-04)
------------------

* Supported any primary key (Contributed by Tony Wang in #11)

0.2.2 (2017-08-02)
------------------

* Supported SQLAlchemy result processor
* Added rich support on JSON/JSONB
* Bug fixes

0.2.1 (2017-07-28)
------------------

* Added ``update`` and ``delete`` API

0.2.0 (2017-07-28)
------------------

* Changed API, no longer reuses asyncpg API

0.1.1 (2017-07-25)
------------------

* Added ``db.bind``
* API changed: parameter ``conn`` renamed to optional ``bind``
* Delegated asyncpg Pool with ``db.create_pool``
* Internal enhancement and bug fixes

0.1.0 (2017-07-21)
------------------

* First release on PyPI.
