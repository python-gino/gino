|GINO| 2
========

.. image:: https://img.shields.io/github/workflow/status/python-gino/gino/test/v2.0.x?label=test&logo=github
        :alt: GitHub Workflow Status for tests
        :target: https://github.com/python-gino/gino/actions?query=workflow%3Atest+branch%3Av2.0.x

.. image:: https://img.shields.io/codacy/coverage/b6a59cdf5ca64eab9104928d4f9bbb97/v2.0.x?logo=codacy
        :alt: Codacy coverage
        :target: https://app.codacy.com/gh/python-gino/gino/dashboard?bid=18025113

.. image:: https://img.shields.io/badge/Dependabot-active-brightgreen?logo=dependabot
        :target: https://app.dependabot.com/accounts/python-gino/projects/129260
        :alt: Dependabot

.. image:: https://img.shields.io/gitter/room/python-gino/Lobby?logo=gitter
        :target: https://gitter.im/python-gino/Lobby
        :alt: Gitter chat

GINO 2 is a copy-n-rewrite of GINO 1.x from scratch.

* Only compatible with the redesigned SQLAlchemy_
  `1.4 <https://docs.sqlalchemy.org/en/14/changelog/migration_14.html>`__ /
  `2.0 <https://docs.sqlalchemy.org/en/14/changelog/migration_20.html>`__
* Support both PostgreSQL_ and MySQL_ from the beginning
* Support both asyncio_ and Trio_
* Complete SQLAlchemy events
* Typing support
* Python 3.7 or above
* Free software: BSD license

+-------------+------------+---------------+
| IO \ DB     | PostgreSQL | MySQL         |
+=============+============+===============+
| **asyncio** | asyncpg_   | aiomysql_     |
+-------------+------------+---------------+
| **Trio**    | triopg_    | `Trio-MySQL`_ |
+-------------+------------+---------------+

Development
-----------

https://github.com/python-gino/gino/projects/1

.. _Trio: https://github.com/python-trio/trio
.. _aiomysql: https://github.com/aio-libs/aiomysql
.. _triopg: https://github.com/python-trio/triopg
.. _Trio-MySQL: https://github.com/python-trio/trio-mysql
.. _SQLAlchemy: https://www.sqlalchemy.org/
.. _asyncpg: https://github.com/MagicStack/asyncpg
.. _PostgreSQL: https://www.postgresql.org/
.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _MySQL: https://www.mysql.com/

.. |GINO| image:: ./docs/theme/static/logo.svg
        :alt: GINO
        :height: 64px
        :target: https://python-gino.org/
