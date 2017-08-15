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

GINO operates database rows with "plain old Python objects" - they *are* just
normal Python objects, a rollback doesn't magically change their values. Any
database operations are explicit - it is crystal clear what is done underneath
each GINO API. There are no dirty models, no sessions, no magic. You have
concrete control to the database, through a convenient object interface. That's
it.

GINO depends on asyncpg_, which means it works only for PostgreSQL_ and
asyncio_, which means Python 3 is required - actually 3.6 required for now.
Based on SQLAlchemy_, gate to its ecosystem is open - feel free to use e.g.
Alembic_ to manage your schema changes. And we specially designed a few candies
for the Sanic_ server.


Example
-------

A piece of code is worth a thousand words:


.. code-block:: python

   import asyncio
   from gino import Gino, enable_task_local

   db = Gino()


   class User(db.Model):
       __tablename__ = 'users'

       id = db.Column(db.Integer(), primary_key=True)
       nickname = db.Column(db.Unicode(), default='noname')


   async def main():
       await db.create_pool('postgresql://localhost/gino')

       # Create object, `id` is assigned by database
       u1 = await User.create(nickname='fantix')
       print(u1.id, u1.nickname)  # 1 fantix

       # Retrieve the same row, as a different object
       u2 = await User.get(u1.id)
       print(u2.nickname)  # fantix

       # Update affects only database row and the operating object
       await u2.update(nickname='daisy').apply()
       print(u2.nickname)  # daisy
       print(u1.nickname)  # fantix

       # Returns all user objects with "d" in their nicknames
       users = await User.query.where(User.nickname.contains('d')).gino.all()

       # Find one user object, None if not found
       user = await User.query.where(User.nickname == 'daisy').gino.first()

       # Execute complex statement and return command status
       status = await User.update.values(
           nickname='No.' + db.cast(User.id, db.Unicode),
       ).where(
           User.id > 10,
       ).gino.status()

       # Iterate over the results of a large query in a transaction as required
       async with db.transaction():
           async for u in User.query.order_by(User.id).gino.iterate():
               print(u.id, u.nickname)


   loop = asyncio.get_event_loop()
   enable_task_local(loop)
   loop.run_until_complete(main())

The code explains a lot, but not everything. Let's go through again briefly.


Declare Models
--------------

Each model maps to a database table. To define a model, you'll need a ``Gino``
object first, usually as a global variable named ``db``. It is actually an
extended instance of ``sqlalchemy.MetaData``, which can be used in Alembic_ for
example. By inheriting from ``db.Model``, you can define database tables in a
declarative way as shown above:

.. code-block:: python

   db = Gino()

   class User(db.Model):
       __tablename__ = 'users'

       id = db.Column(db.Integer(), primary_key=True)
       nickname = db.Column(db.Unicode(), default='noname')

Note that ``__tablename__`` is required, GINO suggests singular for model
names, and plural for table names. After declaration, access to SQLAlchemy
columns is available on class level, allowing vanilla SQLAlchemy programming
like this:

.. code-block:: python

   import sqlalchemy as sa

   sa.select([User.nickname]).where(User.id > 10)

But on object level, model objects are just normal objects in memory. The only
connection to database happens when you explicitly calls a GINO API,
``user.delete`` for example. Otherwise, any changes made to the object stay in
memory only. That said, different objects are isolated from each other, even if
they all map to the same database row - modifying one doesn't affect another.

Speaking of mapping, GINO automatically detects the primary keys and uses them
to identify the correct row in database. This is no magic, it is only a
``WHERE`` clause automatically added to the ``UPDATE`` statement when calling
the ``user.update().apply`` method, or during ``User.get`` retrieval.

.. code-block:: python

   u = await User.get(1)                      # SELECT * FROM users WHERE id = 1
   await u.update(nickname='fantix').apply()  # UPDATE users SET ... WHERE id = 1
   u.id = 2                                   # No SQL here!!
   await u.update(nickname='fantix').apply()  # UPDATE users SET ... WHERE id = 2

Under the hood, model values are stored in a dict named ``__values__``. And the
columns you defined are wrapped with special attribute objects, which deliver
the ``__values__`` to you on object level, or as column objects on class level.


Bind Database
-------------

Though optional, GINO can bind to an asyncpg database connection or pool to
make life easier. The most obvious way is to create a database pool with GINO.

.. code-block:: python

   pool = await db.create_pool('postgresql://localhost/gino')

Once created, the pool is automatically bound to the ``db`` object, therefore
to all the models too. To unplug the database, just close the pool. This API is
identical to the one from asyncpg, so can it be used as a context manager too:

.. code-block:: python

   async with db.create_pool('postgresql://localhost/gino') as pool:
       # play with pool

Otherwise, you will need to manually do the binding:

.. code-block:: python

   import asyncpg

   pool = await asyncpg.create_pool('postgresql://localhost/gino')
   db = Gino(pool)

   # or
   db = Gino()
   db.bind = pool

It is theoretically possible to bind to a connection object, but this scenario
is not normally well tested. And as stated in the beginning, it is possible to
use GINO without binding to a database. In such case, you should manually pass
asyncpg pool or connection object to GINO APIs as the ``bind`` keyword argument:

.. code-block:: python

   import asyncpg
   conn = await asyncpg.connect('postgresql://localhost/gino')
   user = await User.get(3, bind=conn)


At last, GINO can be used to only define models and translate SQLAlchemy
queries into SQL with its builtin asyncpg dialect:

.. code-block:: python

   query, params = db.compile(User.query.where(User.id == 3))
   row = await conn.fetchval(query, *params)


Execute Queries
---------------

There are several levels of API available for use in GINO. On model objects:

.. code-block:: python

   await user.update(nickname='fantix').apply()
   await user.delete()

Please note, ``update`` without ``apply`` only update the object in memory,
while ``apply`` flush the changes to database.

On model class level, to operate objects:

.. code-block:: python

   user = await User.create(nickname='fantix')
   user = await User.get(9)

On model class level, to generate queries:

.. code-block:: python

   query = User.query.where(User.id > 10)
   query = User.select('id', 'nickname')
   query = User.update.values(nickname='fantix').where(User.id = 6)
   query = User.delete.where(User.id = 7)

On query level, GINO adds an extension ``gino`` to run query in place:

.. code-block:: python

   users = await query.gino.all()
   user = await query.gino.first()
   user_id = await query.gino.scalar()

These query APIs are simply delegates to the concrete ones on the ``Gino``
object:

.. code-block:: python

   users = await gino.all(query)
   user = await gino.first(query)
   user_id = await gino.scalar(query)

If the database pool is created by ``db.create_pool``, then such APIs are also
available on the pool object and connection objects:

.. code-block:: python

   async with db.create_pool('...') as pool:
       users = await pool.all(query)
       user = await pool.first(query)
       user_id = await pool.scalar(query)

       async with pool.acquire() as conn:
           users = await conn.all(query)
           user = await conn.first(query)
           user_id = await conn.scalar(query)


Transaction and Context
-----------------------

In normal cases when ``db`` is bound to a pool, you can start a transaction
through ``db`` directly:

.. code-block:: python

   async with db.transaction() as (conn, tx):
       # play within a transaction

As you can see from the unpacked arguments, ``db.transaction()`` acquired a
connection and started a transaction in one go. It is identical to do it
separately:

.. code-block:: python

   async with db.acquire() as conn:
       async with conn.transaction() as tx:
           # play within a transaction

Please note, there is no ``db.release`` to return the connection to the pool,
thus you cannot do ``conn = await db.acquire()``. Using ``async with`` is the
only way, and the reason is about context.

Because GINO offers query APIs on not only connections but also model classes
and objects and even query objects, it would be too much trouble passing
connection object around when dealing with transactions. Therefore GINO offers
an optional feature to automatically manage connection objects, by enabling a
builtin task local hack before any tasks are created:

.. code-block:: python

   from gino import enable_task_local
   enable_task_local()

This switch creates a local storage for each coroutine, where ``db.acquire()``
shall store the connection object. Hence executions within the acquire context
will be able to make use of the same connection right in the local storage.
Furthermore, nested ``db.acquire()`` will simply return the same connection.
This allows ``db.transaction()`` to be nested in the same way that asyncpg
``conn.transaction()`` does it - to use database save points.

.. code-block:: python

   async with db.transaction() as (conn1, tx1):      # BEGIN
       async with db.transaction() as (conn2, tx2):  # SAVEPOINT ...
           assert conn1 == conn2

If nested transactions or reused connections are not expected, you can
explicitly use ``db.acquire(reuse=False)`` or ``db.transaction(reuse=False)``
to borrow new connections from the pool. Non-reused connections are stacked,
they will be returned to the pool in the reversed order as they were borrowed.
Local storage covers between different tasks that are awaited in a chain, it is
theoretically safe in most cases. However it is still some sort of a hack, but
it would be like this before Python officially supports task local storage one
day.


Sanic Support
-------------

To integrate with Sanic_, a few configurations needs to be set in ``app.config`` (with default value though):

- DB_HOST: if not set, ``localhost``
- DB_PORT: if not set, ``5432``
- DB_USER: if not set, ``postgres``
- DB_PASSWORD: if not set, empty string
- DB_DATABASE: if not set, ``postgres``
- DB_POOL_MIN_SIZE: if not set, 5
- DB_POOL_MAX_SIZE: if not set, 10

.. code-block:: python

   from sanic import Sanic
   from sanic.response import json
   from gino.ext.sanic import Gino

   app = Sanic()
   app.config.DB_HOST = 'localhost'
   app.config.DB_USER = 'postgres'

   db = Gino()
   db.init_app(app)


JSON Property
-------------

PostgreSQL started to support native JSON type since 9.2, and became more
feature complete in 9.4. JSON is ideal to store varying key-value data. GINO
offers objective support for this scenario, requiring PostgreSQL 9.5 for now.

.. code-block:: python

   from gino import Gino

   db = Gino()

   class User(db.Model):
       __tablename__ = 'users'

       id = db.Column(db.Integer(), primary_key=True)
       profile = db.Column(db.JSONB())
       nickname = db.StringProperty(default='noname')
       age = db.IntegerProperty()

``nickname`` and ``age`` look just like normal columns, but they are actually
key-value pairs in the ``profile`` column. ``profile`` is the default column
name for JSON properties, you can specify a different name by offering the
argument ``column_name`` when defining a JSON property. Actually multiple JSON
columns are allowed, storing different JSON properties as needed. Also, both
``JSON`` and ``JSONB`` can be used, depending on your choice. For example:

.. code-block:: python

   from gino import Gino

   db = Gino()

   class Article(db.Model):
       __tablename__ = 'articles'

       id = db.Column(db.Integer(), primary_key=True)

       profile = db.Column(db.JSONB())
       author = db.StringProperty(default='noname')
       pub_index = db.IntegerProperty()

       values = db.Column(db.JSON())
       read_count = db.IntegerProperty(default=0, column_name='values')
       last_update = db.DateTimeProperty(column_name='values')

JSON properties work like normal columns too:

.. code-block:: python

   # Create with JSON property values
   u = await User.create(age=18)

   # Default value is immediately available
   u.nickname = 'Name: ' + u.nickname
   # identical to: u.update(nickname='Name' + u.nickname)

   # Updating only age, accept clause:
   await u.update(age=User.age + 2).apply()


Contribute
----------

There are a few tasks in GitHub issues marked as ``help wanted``. Please feel
free to take any of them and pull requests are greatly welcome.

To run tests:

.. code-block:: shell

   python setup.py test


Credits
-------

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
