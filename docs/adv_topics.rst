Advanced Topics
===============

**THIS IS A WIP**

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

There is an alternative to do this without ``async with``, but this may be
changed in next version, as discussed in #59. Also, ``tx`` is always ``None``
for now.

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
it would be like this before Python officially supports task local storage in
PEP 550.


Sanic Support
-------------

To integrate with Sanic_, a few configurations needs to be set in
``app.config`` (with default value though):

- DB_HOST: if not set, ``localhost``
- DB_PORT: if not set, ``5432``
- DB_USER: if not set, ``postgres``
- DB_PASSWORD: if not set, empty string
- DB_DATABASE: if not set, ``postgres``
- DB_POOL_MIN_SIZE: if not set, 5
- DB_POOL_MAX_SIZE: if not set, 10

An example:

.. code-block:: python

   from sanic import Sanic
   from gino.ext.sanic import Gino

   app = Sanic()
   app.config.DB_HOST = 'localhost'
   app.config.DB_USER = 'postgres'

   db = Gino()
   db.init_app(app)


After ``db.init_app``, a connection pool with configured settings shall be
created and bound to ``db`` when Sanic server is started, and closed on stop.
Furthermore, a lazy connection context is created on each request, and released
on response. That is to say, within Sanic request handlers, you can directly
access db by e.g. ``User.get(1)``, everything else is settled: database pool is
created on server start, connection is lazily borrowed from pool on the first
database access and shared within the rest of the same request handler, and
automatically returned to the pool on response.

Please be noted that, in the async world, ``await`` may block unpredictably for
a long time. When this world is crossing RDBMS pools and transactions, it is
a very dangerous bite for performance, even causing disasters sometimes.
Therefore we recommend, during the time enjoying fast development, do pay
special attention to the scope of transactions and borrowed connections, make
sure that transactions are closed as soon as possible, and connections are not
taken for unnecessarily long time. As for the Sanic support, if you want to
release the concrete connection in the request context before response is
reached, just do it like this:

.. code-block:: python

   await request['connection'].release()


Or if you prefer not to use the contextual lazy connection in certain handlers,
prefer explicitly manage the connection lifetime, you can always borrow a new
connection by setting ``reuse=False``:

.. code-block:: python

   async with db.acquire(reuse=False):
       # new connection context is created


Or if you prefer not to use the builtin request-scoped lazy connection at all,
you can simply turn it off:

.. code-block:: python

   app.config.DB_USE_CONNECTION_FOR_REQUEST = False


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
