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

    users = Table('users', metadata,
        Column('id', Integer, primary_key=True),
        Column('name', String),
        Column('fullname', String),
    )

    addresses = Table('addresses', metadata,
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

Here :func:`~gino.create_engine` creates a :class:`~gino.engine.GinoEngine`,
then :meth:`~gino.engine.GinoEngine.acquire` checks out a
:class:`~gino.engine.GinoConnection`, and
:meth:`~gino.engine.GinoConnection.status` executes the insert and returns the
status text. This works similarly as SQLAlchemy
:meth:`sqlalchemy.engine.Connection.execute` - they take the same parameters
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

GINO ORM
--------
