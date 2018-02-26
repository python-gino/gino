====
GINO
====

.. image:: https://img.shields.io/pypi/v/gino.svg
        :target: https://pypi.python.org/pypi/gino

.. image:: https://img.shields.io/travis/fantix/gino/master.svg
        :target: https://travis-ci.org/fantix/gino

.. image:: https://coveralls.io/repos/github/fantix/gino/badge.svg?branch=master
        :target: https://coveralls.io/github/fantix/gino?branch=master

.. image:: https://readthedocs.org/projects/python-gino/badge/?version=latest
        :target: https://python-gino.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://pyup.io/repos/github/fantix/gino/shield.svg
        :target: https://pyup.io/repos/github/fantix/gino/
        :alt: Updates

.. image:: https://img.shields.io/gitter/room/python-gino/Lobby.svg
        :target: https://gitter.im/python-gino/Lobby
        :alt: Gitter chat


GINO - GINO Is Not ORM - is a lightweight asynchronous Python ORM based on
SQLAlchemy_ core. Now (early 2018) GINO supports asyncpg_, Sanic_ and Tornado_.


* Free software: BSD license
* Documentation: https://python-gino.readthedocs.io.

GINO is built on top of SQLAlchemy core, your code will be 100% compatible with
vanilla SQLAlchemy, using Alembic_ for example. GINO defined its own ``Engine``
and ``Connection`` API for asynchronous programming, as well as an asynchronous
dialect API for adapting non-DB-API asynchronous database connectors, asyncpg_
for example. On top of such core, GINO offered an object abstraction API for
simple CRUD operations.

GINO requires Python 3.6 for now, it may be backported to Python 3.5 if time,
but no 3.4 or lower.


Example
-------

A piece of code is worth a thousand words:


.. code-block:: python

   import asyncio
   from gino import Gino

   db = Gino()


   class User(db.Model):
       __tablename__ = 'users'

       id = db.Column(db.Integer(), primary_key=True)
       nickname = db.Column(db.Unicode(), default='noname')


   async def main():
       await db.create_engine('asyncpg://localhost/gino')

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

Please follow the documentation_ for more information.


Contribute
----------

There are a few tasks in GitHub issues marked as ``help wanted``. Please feel
free to take any of them and pull requests are greatly welcome.

To run tests:

.. code-block:: shell

   python setup.py test


Credits
-------

Credit goes to all contributors listed or not listed in the AUTHORS file. This
project is inspired by asyncpgsa_, peewee-async_ and asyncorm_. asyncpg_ and
SQLAlchemy_ as the dependencies did most of the heavy lifting. This package was
created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project
template.

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
.. _documentation: https://python-gino.readthedocs.io/
