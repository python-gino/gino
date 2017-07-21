====
GINO
====


.. image:: https://img.shields.io/pypi/v/gino.svg
        :target: https://pypi.python.org/pypi/gino

.. image:: https://img.shields.io/travis/fantix/gino.svg
        :target: https://travis-ci.org/fantix/gino

.. image:: https://readthedocs.org/projects/gino/badge/?version=latest
        :target: https://gino.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://pyup.io/repos/github/fantix/gino/shield.svg
     :target: https://pyup.io/repos/github/fantix/gino/
     :alt: Updates


GINO Is Not ORM - a Python ORM on asyncpg_ and SQLAlchemy_ core.


* Free software: BSD license
* Documentation: https://gino.readthedocs.io.

There's been a lot of words about ORM a.k.a. Object-relational mapping - good
or bad - as well as a lot of ORM libraries in Python. It is crucial to pick a
most suitable one for your project, and for your team. GINO tries to stay in
the middle between ORM and non-ORM, offering an extremely simple option.

GINO depends on asyncpg_, which means it works only for PostgreSQL_ and
asyncio_, which means Python 3 is required - actually 3.6 required for now.
Based on SQLAlchemy_, gate to its ecosystem is open - feel free to use e.g.
Alembic_ to manage your schema changes. And we specially designed a few candies
for the Sanic_ server.


Features
--------

* Declare SQLAlchemy_ core tables with plain model objects, no ORM magic
* Easily construct queries and execute them through asyncpg_

There're a few usage examples in the examples directory.


Credits
---------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
.. _SQLAlchemy: https://www.sqlalchemy.org/
.. _asyncpg: https://github.com/MagicStack/asyncpg
.. _PostgreSQL: https://www.postgresql.org/
.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _Alembic: https://bitbucket.org/zzzeek/alembic
.. _Sanic: https://github.com/channelcat/sanic
