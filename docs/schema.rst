==================
Schema Declaration
==================

There are 3 ways to declare your database schema to be used with GINO. Because
GINO is built on top of SQLAlchemy core, either way you are actually declaring
SQLAlchemy :class:`~sqlalchemy.schema.Table`.


GINO Engine
-----------

This is the minimized way to use GINO - using only
:class:`~gino.engine.GinoEngine` (and :class:`~gino.engine.GinoConnection`
too), everything else are vanilla SQLAlchemy core. This is useful when you have
legacy code written in SQLAlchemy core, in need of porting to asyncio. For new
code please use the other two.

For example, the table declaration is the same as SQLAlchemy core `tutorial
<https://docs.sqlalchemy.org/en/latest/core/tutorial.html>`_::

    from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey

    metadata = MetaData()

    users = Table(
        'users', metadata,

        Column('id', Integer, primary_key=True),
        Column('name', String),
        Column('fullname', String),
    )

    addresses = Table(
        'addresses', metadata,

        Column('id', Integer, primary_key=True),
        Column('user_id', None, ForeignKey('users.id')),
        Column('email_address', String, nullable=False)
    )

.. note::

    When using GINO Engine only, it is usually your own business to create the
    tables with either :meth:`~sqlalchemy.schema.MetaData.create_all` on a
    normal non-async SQLAlchemy engine, or using Alembic. However it is still
    possible to be done with GINO if it had to::

        import gino
        from gino.schema import GinoSchemaVisitor

        async def main():
            engine = await gino.create_engine('postgresql://...')
            await GinoSchemaVisitor(metadata).create_all(engine)

Then, construct queries, in SQLAlchemy core too::

    ins = users.insert().values(name='jack', fullname='Jack Jones')

So far, everything is still in SQLAlchemy. Now let's get connected and execute
the insert::

    async def main():
        engine = await gino.create_engine('postgresql://localhost/gino')
        conn = await engine.acquire()
        await conn.status(ins)
        print(await conn.all(users.select()))
        # Outputs: [(1, 'jack', 'Jack Jones')]

Here :func:`~gino.create_engine` creates a :class:`~gino.engine.GinoEngine`,
then :meth:`~gino.engine.GinoEngine.acquire` checks out a
:class:`~gino.engine.GinoConnection`, and
:meth:`~gino.engine.GinoConnection.status` executes the insert and returns the
status text. This works similarly as SQLAlchemy
:meth:`~sqlalchemy.engine.Connection.execute` - they take the same parameters
but return a bit differently. There are also other similar query APIs:

* :meth:`~gino.engine.GinoConnection.all` returns a list of
  :class:`~sqlalchemy.engine.RowProxy`
* :meth:`~gino.engine.GinoConnection.first` returns one
  :class:`~sqlalchemy.engine.RowProxy`, or ``None``
* :meth:`~gino.engine.GinoConnection.scalar` returns a single value, or
  ``None``
* :meth:`~gino.engine.GinoConnection.iterate` returns an asynchronous iterator
  which yields :class:`~sqlalchemy.engine.RowProxy`

Please go to their API for more information.


GINO Core
---------

In previous scenario, :class:`~gino.engine.GinoEngine` must not be set to
:attr:`metadata.bind <sqlalchemy.schema.MetaData.bind>` because it is not a
regular SQLAlchemy Engine thus it won't work correctly. For this, GINO provides
a subclass of :class:`~sqlalchemy.schema.MetaData` as :class:`~gino.api.Gino`,
usually instantiated globally under the name of ``db``. It can be used as a
normal :class:`~sqlalchemy.schema.MetaData` still offering some conveniences:

* It delegates most public types you can access on ``sqlalchemy``
* It works with both normal SQLAlchemy engine and asynchronous GINO engine
* It exposes all query APIs on :class:`~gino.engine.GinoConnection` level
* It injects two ``gino`` extensions on SQLAlchemy query clauses and schema
  items, allowing short inline execution like ``users.select().gino.all()``
* It is also the entry for the third scenario, see later

Then we can achieve previous scenario with less code like this::

    from gino import Gino

    db = Gino()

    users = db.Table(
        'users', db,

        db.Column('id', db.Integer, primary_key=True),
        db.Column('name', db.String),
        db.Column('fullname', db.String),
    )

    addresses = db.Table(
        'addresses', db,

        db.Column('id', db.Integer, primary_key=True),
        db.Column('user_id', None, db.ForeignKey('users.id')),
        db.Column('email_address', db.String, nullable=False)
    )

    async def main():
        async with db.with_bind('postgresql://localhost/gino'):
            await db.gino.create_all()
            await users.insert().values(
                name='jack',
                fullname='Jack Jones',
            ).gino.status()
            print(await users.select().gino.all())
            # Outputs: [(1, 'jack', 'Jack Jones')]

Similar to SQLAlchemy core and ORM, this is GINO core. All tables and queries
are still made of SQLAlchemy whose rules still apply, but ``sqlalchemy`` seems
never imported. This is useful when ORM is unwanted.

.. tip::

    `asyncpgsa <https://github.com/CanopyTax/asyncpgsa/>`_ does the same thing,
    but in a conceptually reversed way - instead of having asyncpg work for
    SQLAlchemy, it made SQLAlchemy work for asyncpg (GINO used to be in that
    way too because GINO is inspired by asyncpgsa). Either way works fine, it's
    just a matter of taste of whose API style to use, SQLAlchemy or asyncpg.


GINO ORM
--------

If you want to further reduce the length of code, and taking a bit risk of
implicity, welcome to the ORM world. Even though GINO made itself not quite a
traditional ORM by being simple and explict to safely work with asyncio, common
ORM concepts are still valid - a table is a model class, a row is a model
instance. Still the same example rewritten in GINO ORM::

    from gino import Gino

    db = Gino()


    class User(db.Model):
        __tablename__ = 'users'

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)
        fullname = db.Column(db.String)


    class Address(db.Model):
        __tablename__ = 'addresses'

        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(None, db.ForeignKey('users.id'))
        email_address = db.Column(db.String, nullable=False)


    async def main():
        async with db.with_bind('postgresql://localhost/gino'):
            await db.gino.create_all()
            await User.create(name='jack', fullname='Jack Jones')
            print(await User.query.gino.all())
            # Outputs: [<User object at 0x10a8ba860>]

.. important::

    The ``__tablename__`` is a mandatory field to define a concrete model.

As you can see, the declaration is pretty much the same as before. Underlying
they are identical, declaring two tables in ``db``. The ``class`` style is just
more declarative. Instead of ``users.c.name``, you can now access the column by
``User.name``. The implicitly created :class:`~sqlalchemy.schema.Table` is
available at ``User.__table__`` and ``Address.__table__``. You can use anything
that works in GINO core here.

.. note::

    Column names can be different as a class property and database column.
    For example, name can be declared as
    ``nickname = db.Column('name', db.Unicode(), default='noname')``. In this
    example, ``User.nickname`` is used to access the column, while in database,
    the column name is ``name``.

    What's worth mentioning is where raw SQL statements are used, or
    ``TableClause`` is involved, like ``User.insert()``, the original name is
    required to be used, because in this case, GINO has no knowledge about the
    mappings.

.. tip::

    ``db.Model`` is a dynamically created parent class for your models. It is
    associated with the ``db`` on initialization, therefore the table is put in
    the very ``db`` when you declare your model class.

Things become different when it comes to CRUD. You can use model level methods
to directly :meth:`~gino.crud.CRUDModel.create` a model instance, instead of
inserting a new row. Or :meth:`~gino.crud.CRUDModel.delete` a model instance
without needing to specify the where clause manually. Query returns model
instances instead of :class:`~sqlalchemy.engine.RowProxy`, and row values are
directly available as attributes on model instances. See also: :doc:`/crud`.

After all, :class:`~gino.engine.GinoEngine` is always in use. Next let's dig
more into it.
