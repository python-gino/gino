====
GINO
====


.. image:: https://img.shields.io/pypi/v/gino.svg
        :target: https://pypi.python.org/pypi/gino

.. image:: https://img.shields.io/travis/fantix/gino.svg
        :target: https://travis-ci.org/fantix/gino

.. image:: https://readthedocs.org/projects/ginorm/badge/?version=latest
        :target: https://ginorm.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://pyup.io/repos/github/fantix/gino/shield.svg
     :target: https://pyup.io/repos/github/fantix/gino/
     :alt: Updates


GINO - GINO Is Not ORM - is an extremely simple Python ORM, using SQLAlchemy_
core to define table models, and asyncpg_ to interact with database.


* Free software: BSD license
* Documentation: https://gino.readthedocs.io.

There's been a lot of words about ORM a.k.a. Object-relational mapping - good
or bad - as well as a lot of ORM libraries in Python. It is crucial to pick a
most suitable one for your project, and for your team. GINO tries to stay in
the middle between ORM and non-ORM, offering an extremely simple option.

GINO tries to define database tables with plain old Python objects - they *are*
normal Python objects, a rollback doesn't magically change their values. Any
database operations are explicit. It is crystal clear what is done underneath
each GINO API. There are no dirty models, no sessions, no magic. You have
concrete control to the database, through a convenient object interface. That's
it.

GINO depends on asyncpg_, which means it works only for PostgreSQL_ and
asyncio_, which means Python 3 is required - actually 3.6 required for now.
Based on SQLAlchemy_, gate to its ecosystem is open - feel free to use e.g.
Alembic_ to manage your schema changes. And we specially designed a few candies
for the Sanic_ server.

Basic Usage
-----------

A piece of code is worth a thousand words:


.. code-block:: python

   from gino import Gino
   from sqlalchemy import Column, BigInteger, Unicode

   db = Gino()


   class User(db.Model):
       __tablename__ = 'users'

       id = Column(BigInteger(), primary_key=True)
       nickname = Column(Unicode(), default='noname')


This is quite similar to SQLAlchemy ORM, but it is actually SQLAlchemy core:

* ``db = Gino()`` is actually a ``sqlalchemy.MetaData`` object
* ``class User`` actually defines a ``sqlalchemy.Table`` at ``User.__table__``

Other than that, ``User`` is just a normal Python object:


.. code-block:: python

   u = User()
   u.id = 7
   u.id += 2
   u.nickname = 'fantix'


Think as if ``User`` is defined normally (keep in imagination, not an example):


.. code-block:: python

   class User:
       def __init__(self):
           self.id = None
           self.nickname = None


However on class level, you have access to SQLAlchemy columns, which allows you
to do SQLAlchemy core programming:


.. code-block:: python

   from sqlalchemy import select
   query = select([User.nickname]).where(User.id == 9)


The ``Gino`` object offers a SQLAlchemy dialect for asyncpg, allowing to
execute the query in asyncpg:


.. code-block:: python

   import asyncpg
   conn = await asyncpg.connect('postgresql://localhost/gino')

   query, params = db.compile(query)
   rv = await conn.fetchval(query, *params)


ORM Sugars
----------

Though it is possible to use GINO as a SQLAlchemy core async wrapper by using
only ``db.Model`` and ``db.compile``, it would make life much easier if GINO
sugars for ORM are considered. First of all, it is preferred to bind an
``asyncpg.Pool`` to the ``Gino`` object, by creating a pool through a delegated
API, following the same example above:

.. code-block:: python

   async with db.create_pool('postgresql://localhost/gino') as pool:


Because the models are defined with the same ``db`` object, they are
automatically bound to the database pool, allowing such CRUD operations:

.. code-block:: python

   u1 = await User.get(9)
   u2 = await User.create(nickname=u1.nickname))
   await u2.update(nickname='daisy')
   await u1.delete()


A note here: GINO has no ``u2.save()``. Therefore ``u2.nickname = 'daisy'``
does not execute any SQL but only modify memory value - use ``u2.update`` to
both run an ``UPDATE`` SQL and modify memory value. Correspondingly,
``u1.delete()`` only deletes the row in database, but leaving the object in
memory untouched.

The ``Gino`` object ``db`` also offers a few more objective APIs for queries,
corresponding to asyncpg APIs:

.. code-block:: python

   # returns all user objects with "d" in their nicknames
   users = await db.all(User.query.where(User.nickname.contains('d')))

   # find one user object, None if not found
   user = await db.first(User.query.where(User.nickname == 'daisy'))


Or progressively load objects from a large query, in a transaction as required:

.. code-block:: python

   async with db.transaction() as (conn, tx):
       async for u in db.iterate(User.query, connection=conn):
           print(u.id, u.nickname)


Contribute
----------

There are a few tasks in GitHub issues marked as ``help wanted``. Please feel
free to take any of them and pull requests are greatly welcome.

To run tests:

.. code-block:: shell

   python setup.py test


Credits
---------

Credit goes to all contributors listed in the AUTHORS file. This project is
inspired by asyncpgsa_, peewee-async_ and asyncorm_. asyncpg_ and SQLAlchemy_
as the dependencies did most of the heavy lifting. This package was created
with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

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
