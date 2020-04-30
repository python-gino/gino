Bake Queries
============

Baked queries are used to boost execution performance for constantly-used queries.
Similar to the :doc:`orm/extensions/baked` in SQLAlchemy, GINO could also cache the
object’s construction and string-compilation steps. Furthermore, GINO automatically
manages a prepared statement for each baked query in every active connection in the
pool. Executing baked queries is at least 40% faster than running normal queries, but
you need to bake them before creating the engine.

GINO provides two approaches for baked queries:

1. Low-level :class:`~gino.bakery.Bakery` API
2. High-level :meth:`Gino.bake() <gino.api.Gino.bake>` integration


Use Bakery with Bare Engine
---------------------------

First, we need a bakery::

    import gino

    bakery = gino.Bakery()

Then, let's bake some queries::

    db_time = bakery.bake("SELECT now()")

Or queries with parameters::

    user_query = bakery.bake("SELECT * FROM users WHERE id = :uid")

Let's assume we have this ``users`` table defined in SQLAlchemy Core::

    import sqlalchemy as sa

    metadata = sa.MetaData()
    user_table = sa.Table(
        "users", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String),
    )

Now we can bake a similar query with SQLAlchemy Core::

    user_query = bakery.bake(
        sa.select([user_table]).where(user.c.id == sa.bindparam("uid"))
    )

These baked queries are usually global, and supposed to be shared across the
application. To run them, we need an engine with the bakery::

    engine = await gino.create_engine("postgresql://localhost/", bakery=bakery)

By doing so, GINO will bake the queries in the bakery. As new connections are added to
the DB pool, the prepared statements are automatically created behind the scene.

To execute the baked queries, you could treat the :class:`~gino.bakery.BakedQuery`
instances as if they are the queries themselves, for example::

    now = await engine.scalar(db_time)

Pass in parameter values::

    row = await engine.first(user_query, uid=123)


Use the :class:`~gino.api.Gino` Integration
--------------------------------------------

In a more common scenario, there will be a :class:`~gino.api.Gino>` instance, which has
usually a ``bind`` set - either explicitly or by the Web framework extensions::

    from gino import Gino

    db = Gino()

    async def main():
        async with db.with_bind("postgresql://localhost/"):
            ...

A :class:`~gino.bakery.Bakery` is automatically created in the ``db`` instance, and fed
to the engine implicitly. You can immediately start to bake queries without further
ado::

    class User(db.Model):
        __tablename__ = "users"

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(sa.String)

    db_time = db.bake("SELECT now()")
    user_getter = db.bake(User.query.where(User.id == db.bindparam("uid")))

And the execution is also simplified with the same ``bind`` magic::

    async def main():
        async with db.with_bind("postgresql://localhost/"):
            print(await db_time.scalar())

            user: User = await user_getter.first(uid=1)
            print(user.name)


How to customize loaders?
-------------------------

If possible, you could bake the additional execution options into the query::

    user_getter = db.bake(
        User.query.where(User.id == db.bindparam("uid")).execution_options(
            loader=User.load(comment="Added by loader.")
        )
    )

The :meth:`~gino.bakery.Bakery.bake` method accepts keyword arguments as execution
options to e.g. simplify the example above into::

    user_getter = db.bake(
        User.query.where(User.id == db.bindparam("uid")),
        loader=User.load(comment="Added by loader."),
    )

If the query construction is complex, :meth:`~gino.bakery.Bakery.bake` could also be
used as a decorator::

    @db.bake
    def user_getter():
        return User.query.where(User.id == db.bindparam("uid")).execution_options(
            loader=User.load(comment="Added by loader.")
        )

Or with short execution options::

    @db.bake(loader=User.load(comment="Added by loader."))
    def user_getter():
        return User.query.where(User.id == db.bindparam("uid"))

Meanwhile, it is also possible to override the loader at runtime::

    user: User = await user_getter.load(User).first(uid=1)
    print(user.name)  # no more comment on user!

.. hint::

    This override won't affect the baked query - it's used only in this execution.


What APIs are available on :class:`~gino.bakery.BakedQuery`?
------------------------------------------------------------

:class:`~gino.bakery.BakedQuery` is a :class:`~gino.api.GinoExecutor`, so it inherited
all the APIs like :meth:`~gino.api.GinoExecutor.all`,
:meth:`~gino.api.GinoExecutor.first`, :meth:`~gino.api.GinoExecutor.one`,
:meth:`~gino.api.GinoExecutor.one_or_none`, :meth:`~gino.api.GinoExecutor.scalar`,
:meth:`~gino.api.GinoExecutor.status`, :meth:`~gino.api.GinoExecutor.load`,
:meth:`~gino.api.GinoExecutor.timeout`, etc.

:class:`~gino.api.GinoExecutor` is actually the chained ``.gino`` helper API seen
usually in queries like this::

    user = await User.query.where(User.id == 123).gino.first()

So a :class:`~gino.bakery.BakedQuery` can be seen as a normal query with the ``.gino``
suffix, plus it is directly executable.

.. seealso::

    Please see API document of :mod:`gino.bakery` for more information.
