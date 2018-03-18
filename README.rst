====
GINO
====

.. image:: https://img.shields.io/pypi/v/gino.svg
        :target: https://pypi.python.org/pypi/gino

.. image:: https://img.shields.io/travis/fantix/gino/master.svg
        :target: https://travis-ci.org/fantix/gino

.. image:: https://img.shields.io/coveralls/github/fantix/gino/master.svg
        :target: https://coveralls.io/github/fantix/gino?branch=master

.. image:: https://img.shields.io/readthedocs/python-gino/stable.svg
        :target: https://python-gino.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://pyup.io/repos/github/fantix/gino/shield.svg
        :target: https://pyup.io/repos/github/fantix/gino/
        :alt: Updates

.. image:: https://img.shields.io/gitter/room/python-gino/Lobby.svg
        :target: https://gitter.im/python-gino/Lobby
        :alt: Gitter chat


GINO - GINO Is Not ORM - is a lightweight asynchronous ORM built on top of
SQLAlchemy_ core for Python asyncio_. Now (early 2018) GINO supports only one
dialect asyncpg_.

* Free software: BSD license
* Requires: Python 3.6


Documentation
-------------

* English_
* Chinese_


Features
--------

* Robust SQLAlchemy-asyncpg bi-translator with no hard hack
* Asynchronous SQLAlchemy-alike engine and connection
* Asynchronous dialect API
* Asynchronous-friendly CRUD objective models
* Well-considered contextual connection and transaction management
* Reusing native SQLAlchemy core to build queries with grammar sugars
* Support Sanic_ and Tornado_
* Rich PostgreSQL JSONB support


Showcase
--------

.. code-block:: python

   import asyncio
   from gino import Gino

   db = Gino()


   class User(db.Model):
       __tablename__ = 'users'

       id = db.Column(db.Integer(), primary_key=True)
       nickname = db.Column(db.Unicode(), default='noname')


   async def main():
       await db.set_bind('postgresql://localhost/gino')

       # Create tables
       await db.gino.create_all()

       # Create object, `id` is assigned by database
       u1 = await User.create(nickname='fantix')
       print(u1.id, u1.nickname)  # 1 fantix

       # Returns all user objects with "d" in their nicknames
       users = await User.query.where(User.nickname.contains('d')).gino.all()
       print(users)  # [<User object>, <User object>]

       # Find one user object, None if not found
       user = await User.query.where(User.nickname == 'daisy').gino.first()
       print(user)  # <User object> or None

       # Execute complex statement and return command status
       status, result = await User.update.values(
           nickname='No.' + db.cast(User.id, db.Unicode),
       ).where(
           User.id > 10,
       ).gino.status()
       print(status)  # UPDATE 8

       # Iterate over the results of a large query in a transaction as required
       async with db.transaction():
           async for u in User.query.order_by(User.id).gino.iterate():
               print(u.id, u.nickname)


   asyncio.get_event_loop().run_until_complete(main())


About The Name
--------------

About the name GINO Is Not ORM - because I don't really like ORM (smile). GINO
does perform the Object-Relational Mapping work under the
`Data Mapper Pattern <https://en.wikipedia.org/wiki/Data_mapper_pattern>`_, but
it is just not a traditional ORM. The Objects in GINO are completely stateless
from database - they are pure plain Python objects in memory. Changing their
attribute values does not make them "dirty" - or in a different way of thinking
they are always "dirty". Any access to database must be explicitly executed.
Using GINO is more like making up SQL clauses with Models and Objects,
executing them to make changes in database, or loading data from database and
wrapping the results with Objects again. Objects are just row data containers,
you are still dealing with SQL which is represented by Models and SQLAlchemy
core grammars. Besides if you don't like ORM at all, you can use GINO without
ORM:

.. code-block:: python

    import sqlalchemy as sa

    metadata = sa.MetaData()

    user = sa.Table(
        'users', metadata,
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('nickname', sa.Unicode()),
    )


    import gino

    async def main():
        e = await gino.create_engine('postgresql://localhost/gino')
        users = await e.all(sa.select([user]))
        print(users)
        # prints something like this:
        # [(1, 'fantix'), (2, 'fantix'), (3, 'fantix'), (5, 'fantix')]


    import asyncio

    asyncio.get_event_loop().run_until_complete(main())

or a bit more GINO-ish:

.. code-block:: python

    from gino import Gino

    db = Gino()

    user = db.Table(
        'users', db,
        db.Column('id', db.BigInteger(), primary_key=True),
        db.Column('nickname', db.Unicode()),
    )

    async def main():
        async with db.with_bind('postgresql://localhost/gino'):
            users = await db.select([user]).gino.all()
            print(users)


    import asyncio

    asyncio.get_event_loop().run_until_complete(main())


Contribute
----------

There are a few tasks in GitHub issues marked as ``help wanted``. Please feel
free to take any of them and pull requests are greatly welcome.

To run tests:

.. code-block:: console

   $ python setup.py test


Credits
-------

Credit goes to all contributors listed or not listed in the AUTHORS file. This
project is inspired by asyncpgsa_, peewee-async_ and asyncorm_. asyncpg_ and
SQLAlchemy_ as the dependencies did most of the heavy lifting. This package was
created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project
template.

Special thanks to my wife Daisy and her outsourcing company `DecentFoX Studio`_,
for offering me the opportunity to build this project. We are open for global
software project outsourcing on Python, iOS and Android development.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
.. _SQLAlchemy: https://www.sqlalchemy.org/
.. _asyncpg: https://github.com/MagicStack/asyncpg
.. _PostgreSQL: https://www.postgresql.org/
.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _Alembic: https://bitbucket.org/zzzeek/alembic
.. _Sanic: https://github.com/channelcat/sanic
.. _asyncpgsa: https://github.com/CanopyTax/asyncpgsa
.. _peewee-async: https://github.com/05bit/peewee-async
.. _asyncorm: https://github.com/monobot/asyncorm
.. _Tornado: http://www.tornadoweb.org/
.. _English: https://python-gino.readthedocs.io/
.. _Chinese: https://python-gino.readthedocs.io/zh/latest/
.. _DecentFoX Studio: https://decentfox.com/
