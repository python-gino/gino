=======
History
=======

0.2.3 (2017-08-04)
------------------

* Support any primary key (Contributed by Tony Wang in #11)

0.2.2 (2017-08-02)
------------------

* Support SQLAlchemy result processor
* Added rich support on JSON/JSONB
* Bug fixes

0.2.1 (2017-07-28)
------------------

* Added `update` and `delete` API

0.2.0 (2017-07-28)
------------------

* Changed API, no longer reuses asyncpg API

0.1.1 (2017-07-25)
------------------

* Added `db.bind`
* API changed: parameter `conn` renamed to optional `bind`
* Delegated asyncpg Pool with `db.create_pool`
* Internal enhancement and bug fixes

0.1.0 (2017-07-21)
------------------

* First release on PyPI.
