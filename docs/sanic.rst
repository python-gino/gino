=============
Sanic Support
=============

**THIS IS A WIP**


Work with Sanic
---------------

Using the Sanic extension, the request handler acquires a lazy connection on each request,
and return the connection when the response finishes by default.

The lazy connection is actually established if necessary, i.e. just before first access to db.

This behavior is controlled by app.config.DB_USE_CONNECTION_FOR_REQUEST, which is True by default.

Supported configurations:

- DB_HOST
- DB_PORT
- DB_USER
- DB_PASSWORD
- DB_DATABASE
- DB_ECHO
- DB_POOL_MIN_SIZE
- DB_POOL_MAX_SIZE
- DB_USE_CONNECTION_FOR_REQUEST

An example server:

::

    from sanic import Sanic
    from sanic.exceptions import abort
    from sanic.response import json
    from gino.ext.sanic import Gino

    app = Sanic()
    app.config.DB_HOST = 'localhost'
    app.config.DB_DATABASE = 'gino'
    db = Gino()
    db.init_app(app)


    class User(db.Model):
        __tablename__ = 'users'

        id = db.Column(db.BigInteger(), primary_key=True)
        nickname = db.Column(db.Unicode())

        def __repr__(self):
            return '{}<{}>'.format(self.nickname, self.id)


    @app.route("/users/<user_id>")
    async def get_user(request, user_id):
        if not user_id.isdigit():
            abort(400, 'invalid user id')
        user = await User.get_or_404(int(user_id))
        return json({'name': user.nickname})


    if __name__ == '__main__':
        app.run(debug=True)


Sanic Support
-------------

To integrate with Sanic, a few configurations needs to be set in
``app.config`` (with default value though):

- DB_HOST: if not set, ``localhost``
- DB_PORT: if not set, ``5432``
- DB_USER: if not set, ``postgres``
- DB_PASSWORD: if not set, empty string
- DB_DATABASE: if not set, ``postgres``
- DB_ECHO: if not set, ``False``
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


