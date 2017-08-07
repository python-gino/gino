=======
History
=======

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
