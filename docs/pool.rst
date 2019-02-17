===============
Connection Pool
===============


Other than the default connection pool, alternative pools can be used in
their own use cases.
There are options from dialects (currently only
:class:`~gino.dialects.asyncpg.NullPool`), and users can define their own pools.
The base class should be :class:`~gino.dialects.base.Pool`.

To use non-default pools in raw GINO::

    from gino.dialects.asyncpg import NullPool
    create_engine('postgresql://...', pool_class=NullPool)

To use non-default pools in extensions (taking Sanic as an example)::

    from gino.dialects.asyncpg import NullPool
    from gino.ext.sanic import Gino

    app = sanic.Sanic()
    app.config.DB_HOST = 'localhost'
    app.config.DB_KWARGS = dict(
        pool_class=NullPool,
    )
    db = Gino()
    db.init_app(app)
