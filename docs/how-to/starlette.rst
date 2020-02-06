=================
Starlette Support
=================

**THIS IS A WIP**

Work with Starlette
-------------------
To use GINO with Starlette, the gino-starlette package should
be installed first:

.. code-block:: console

    pip install gino-starlette

    Note: gino-starlette only supports GINO 1.0 or later.
    Earlier version like 0.8.x has starlette support by itself.
    The usage of any version is backward-compatible.

GINO adds a middleware to the Starlette app to setup and cleanup
database according to the configurations that passed in the ``kwargs``
parameter.
The common usage looks like this:

.. code-block:: python

    from starlette.applications import Starlette
    from gino.ext.starlette import Gino

    app = Starlette()
    db = Gino(app, **kwargs)

    # Or with application factory
    app = Starlette()
    db = Gino(**kwargs)
    db.init_app(app)

Configuration
-------------

| The config includes:

+----------------------------------+-----------------------------------------------------------------------------------------------------------------------+-----------------+
| Name                             | Description                                                                                                           | Default         |
+==================================+=======================================================================================================================+=================+
| ``driver``                       | the database driver                                                                                                   | ``asyncpg``     |
+----------------------------------+-----------------------------------------------------------------------------------------------------------------------+-----------------+
| ``host``                         | database server host                                                                                                  | ``localhost``   |
+----------------------------------+-----------------------------------------------------------------------------------------------------------------------+-----------------+
| ``port``                         | database server port                                                                                                  | ``5432``        |
+----------------------------------+-----------------------------------------------------------------------------------------------------------------------+-----------------+
| ``user``                         | database server user                                                                                                  | ``postgres``    |
+----------------------------------+-----------------------------------------------------------------------------------------------------------------------+-----------------+
| ``password``                     | database server password                                                                                              | empty           |
+----------------------------------+-----------------------------------------------------------------------------------------------------------------------+-----------------+
| ``database``                     | database name                                                                                                         | ``postgres``    |
+----------------------------------+-----------------------------------------------------------------------------------------------------------------------+-----------------+
| ``dsn``                          | a SQLAlchemy database URL to create the engine, its existence will replace all previous connect arguments.            | N/A             |
+----------------------------------+-----------------------------------------------------------------------------------------------------------------------+-----------------+
| ``pool_min_size``                | the initial number of connections of the db pool.                                                                     | N/A             |
+----------------------------------+-----------------------------------------------------------------------------------------------------------------------+-----------------+
| ``pool_max_size``                | the maximum number of connections in the db pool.                                                                     | N/A             |
+----------------------------------+-----------------------------------------------------------------------------------------------------------------------+-----------------+
| ``echo``                         | enable SQLAlchemy echo mode.                                                                                          | N/A             |
+----------------------------------+-----------------------------------------------------------------------------------------------------------------------+-----------------+
| ``ssl``                          | SSL context passed to ``asyncpg.connect``                                                                             | ``None``        |
+----------------------------------+-----------------------------------------------------------------------------------------------------------------------+-----------------+
| ``use_connection_for_request``   | flag to set up lazy connection for requests.                                                                          | N/A             |
+----------------------------------+-----------------------------------------------------------------------------------------------------------------------+-----------------+
| ``kwargs``                       | other parameters passed to the specified dialects, like ``asyncpg``. Unrecognized parameters will cause exceptions.   | N/A             |
+----------------------------------+-----------------------------------------------------------------------------------------------------------------------+-----------------+

Lazy Connection
---------------

If ``use_connection_for_request`` is set to be True, then a lazy
connection is available at ``request['connection']``. By default, a
database connection is borrowed on the first query, shared in the same
execution context, and returned to the pool on response. If you need to
release the connection early in the middle to do some long-running
tasks, you can simply do this:

.. code:: python

    await request['connection'].release(permanent=False)