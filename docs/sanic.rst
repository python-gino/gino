=============
Sanic Support
=============

**THIS IS A WIP**

Check examples directory for general usage.


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
