=======
History
=======

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
