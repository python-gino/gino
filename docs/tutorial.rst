Get Started
===========

This tutorial helps beginners to get started with the basic part of GINO.
Target audiences of this tutorial should have basic knowledge of:

* RDBMS, especially PostgreSQL_
* Asynchronous programming in Python

Knowledge of SQLAlchemy_ is not required.

.. _PostgreSQL: https://www.postgresql.org/


Introduction
------------

Simply speaking, GINO helps you write and execute raw SQL in your asynchronous
application. Instead of interacting RDBMS directly with raw SQL, you can access
your data through friendly objective API.

You may not need GINO, or else to say asynchronous database connection, because
it adds quite some complexity and risk to your stack, and it won't make your
code run faster, if not slower. Please read :doc:`why` for more information.


Installation
------------

.. note::

    GINO optionally depends on aiocontextvars_ for sharing connection between
    method calls or chained coroutines without passing the connection object
    over and over again. It is highly recommended for most projects, unless you
    truly need a bare environment and handle connections manually.

.. _aiocontextvars: https://github.com/fantix/aiocontextvars


Stable release
^^^^^^^^^^^^^^

To install GINO, run this command in your terminal:

.. code-block:: console

    $ pip install gino aiocontextvars

This is the preferred method to install GINO, as it will always install the
most recent stable release.

If you don't have `pip`_ installed, this `Python installation guide`_ can guide
you through the process.

.. _pip: https://pip.pypa.io
.. _Python installation guide: http://docs.python-guide.org/en/latest/starting/installation/


From sources
^^^^^^^^^^^^

The sources for GINO can be downloaded from the `Github repo`_.

You can either clone the public repository:

.. code-block:: console

    $ git clone git://github.com/fantix/gino

Or download the `tarball`_:

.. code-block:: console

    $ curl  -OL https://github.com/fantix/gino/tarball/master

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ python setup.py install


.. _Github repo: https://github.com/fantix/gino
.. _tarball: https://github.com/fantix/gino/tarball/master


Declare Models
--------------

First of all, we'll need a :class:`~gino.api.Gino` object, usually under the
name of ``db`` as a global variable::

    from gino import Gino

    db = Gino()

``db`` acts like a reference to the database, most database interactions will
go through it.

"Model" is a basic concept in GINO, it is a Python class inherited from
:attr:`db.Model <gino.api.Gino.Model>`. Each :class:`~gino.declarative.Model`
subclass maps to one table in the database, while each object of the class
represents one row in the table. This must feel familiar if ORM is not a
strange word to you. Now let's declare a model::

    class User(db.Model):
        __tablename__ = 'users'

        id = db.Column(db.Integer(), primary_key=True)
        nickname = db.Column(db.Unicode(), default='noname')

By declaring this ``User`` class, we are actually defining a database table
named ``users``, with two columns ``id`` and ``nickname``. Note that the fixed
:attr:`~gino.declarative.Model.__tablename__` property is required. GINO
suggests singular for model names, and plural for table names. Each
:class:`db.Column <sqlalchemy.schema.Column>` property defines one column for
the table, where its first parameter indicates the column type in database,
while the rest is for other column attributes or constraints. You can find a
mapping of database types to ``db`` types `here
<http://docs.sqlalchemy.org/en/latest/core/type_basics.html>`_ in SQLAlchemy
document.

.. note::

    SQLAlchemy_ is a powerful ORM library for non-asynchronous programming in
    Python, on top of which GINO is built. SQLAlchemy supports many popular
    RDBMS including PostgreSQL and MySQL through different dialect
    implementation, so that the same Python code can be compiled into different
    SQL depending on the dialect you choose. GINO inherited this support too,
    but for now there is only one dialect for PostgreSQL through asyncpg_.

.. _asyncpg: https://github.com/MagicStack/asyncpg
.. _SQLAlchemy: https://www.sqlalchemy.org/


Get Connected
-------------

The declaration only defined the mapping, it does not create the actual table
in the database. To do that, we need to get connected first. Let's create a
PostgreSQL database for this tutorial:

.. code-block:: console

    $ createdb gino

Then we tell our ``db`` object to connect to this database::

    import asyncio

    async def main():
        await db.set_bind('postgresql://localhost/gino')

    asyncio.get_event_loop().run_until_complete(main())

If this runs successfully, then you are connected to the newly created database.
Here ``asyncpg`` indicates the database dialect and driver to use, ``localhost``
is where the server is, and ``gino`` is the name of the database. Check
`here <https://docs.sqlalchemy.org/en/latest/core/engines.html>`_ for more
information about how to compose this database URL.

.. note::

    Under the hood :meth:`~gino.api.Gino.set_bind` calls
    :func:`~gino.create_engine` and bind the engine to this ``db`` object. GINO
    engine is similar to SQLAlchemy engine, but not identical. Because GINO
    engine is asynchronous, while the other is not. Please refer to the API
    reference of GINO for more information.

Now that we are connected, let's create the table in database (in the same
``main()`` method)::

    await db.gino.create_all()

.. warning::

    It is :meth:`db.gino.create_all <gino.schema.GinoSchemaVisitor.create_all>`,
    not :meth:`db.create_all <sqlalchemy.schema.MetaData.create_all>`, because
    ``db`` is inherited from SQLAlchemy :class:`~sqlalchemy.schema.MetaData`,
    and :meth:`db.create_all <sqlalchemy.schema.MetaData.create_all>` is from
    SQLAlchemy using non-asynchronous methods, which doesn't work with the
    bound GINO engine.

    In practice :meth:`~gino.schema.GinoSchemaVisitor.create_all` is usually
    not an ideal solution. To manage database schema, tool like Alembic_ is
    recommended.

If you want to explicitly disconnect from the database, you can do this::

    await db.pop_bind().close()

Let's review the code we have so far together in one piece before moving on::

    import asyncio
    from gino import Gino

    db = Gino()


    class User(db.Model):
        __tablename__ = 'users'

        id = db.Column(db.Integer(), primary_key=True)
        nickname = db.Column(db.Unicode(), default='noname')


    async def main():
        await db.set_bind('postgresql://localhost/gino')
        await db.gino.create_all()

        # further code goes here

        await db.pop_bind().close()


    asyncio.get_event_loop().run_until_complete(main())

.. _Alembic: https://bitbucket.org/zzzeek/alembic


CRUD Operations
---------------

In order to operate on the database, one of GINO's core features is to Create,
Retrieve, Update or Delete model objects, also known as the CRUD operations.


Create
^^^^^^

Let's start by creating a ``User``::

    user = await User.create(nickname='fantix')
    # This will cause GINO to execute this SQL with parameter 'fantix':
    # INSERT INTO users (nickname) VALUES ($1) RETURNING users.id, users.nickname

As mentioned previously, ``user`` object represents the newly created row in
the database. You can get the value of each columns by the declared column
properties on the object::

    print(f'ID:       {user.id}')           # 1
    print(f'Nickname: {user.nickname}')     # fantix


Retrieve
^^^^^^^^

To retrieve a model object from database by primary key, you can use the class
method :meth:`~gino.crud.CRUDModel.get` on the model class. Now let's retrieve
the same row::

    user = await User.get(1)
    # SQL (parameter: 1):
    # SELECT users.id, users.nickname FROM users WHERE users.id = $1

Normal SQL queries are done through a class property
:attr:`~gino.crud.CRUDModel.query`. For example, let's retrieve all ``User``
objects from database as a list::

    all_users = await db.all(User.query)
    # SQL:
    # SELECT users.id, users.nickname FROM users

Alternatively, you can use the ``gino`` extension on
:attr:`~gino.crud.CRUDModel.query. This has exactly the same effect as above::

    all_users = await User.query.gino.all()
    # SQL:
    # SELECT users.id, users.nickname FROM users

.. note::

    ``User.query`` is actually a SQLAlchemy query, with its own
    non-asynchronous execution methods. GINO added this ``gino`` extension on
    all executable SQLAlchemy clause objects to conveniently execute them in
    the asynchronous way, so that it is even not needed to import the ``db``
    reference for execution.

Now let's add some filters. For example, find all users with ID lower than 10::

    founding_users = await User.query.where(User.id < 10).gino.all()
    # SQL (parameter: 10):
    # SELECT users.id, users.nickname FROM users WHERE users.id < $1

Read more `here <https://docs.sqlalchemy.org/en/latest/core/expression_api.html>`_
about writing queries, because the query object is exactly from SQLAlchemy core.

.. warning::

    Once you get a model object, it is purely in memory and fully detached from
    the database. That means, if the row is externally updated, the object
    values remain unchanged. Likewise, changes made to the object won't affect
    the database values.

    Also, GINO keeps no track of model objects, therefore getting the same row
    twice returns two different object with identical values. Modifying one
    does not magically affect the other one.

    Different than traditional ORMs, the GINO model objects are more like
    objective SQL results, rather than stateful ORM objects. In order to adapt
    for asynchronous programming, GINO is designed to be that simple. That's
    also why GINO Is Not ORM.

Sometimes we want to get only one object, for example getting the user by name
when logging in. There's a shortcut for this scenario::

    user = await User.query.where(User.nickname == 'fantix').gino.first()
    # SQL (parameter: 'fantix'):
    # SELECT users.id, users.nickname FROM users WHERE users.nickname = $1

If there is no user named "fantix" in database, ``user`` will be ``None``.

And sometimes we may want to get a single value from database, getting the name
of user with ID 1 for example. Then we can use the
:meth:`~gino.crud.CRUDModel.select` class method::

    name = await User.select('nickname').where(User.id == 1).gino.scalar()
    # SQL (parameter: 1):
    # SELECT users.nickname FROM users WHERE users.id = $1
    print(name)  # fantix

Or get the count of all users::

    population = await db.func.count(User.id).gino.scalar()
    # SQL:
    # SELECT count(users.id) AS count_1 FROM users
    print(population)  # 17 for example


Update
^^^^^^

Then let's try to make some modifications. In this example we'll mixin some
retrieve operations we just tried. ::

    # create a new user
    user = await User.create(nickname='fantix')

    # get its name
    name = await User.select('nickname').where(
        User.id == user.id).gino.scalar()
    assert name == user.nickname  # they are both 'fantix' before the update

    # modification here
    await user.update(nickname='daisy').apply()
    # SQL (parameters: 'daisy', 1):
    # UPDATE users SET nickname=$1 WHERE users.id = $2 RETURNING users.nickname
    print(user.name)  # daisy

    # get its name again
    name = await User.select('nickname').where(
        User.id == user.id).gino.scalar()
    print(name)  # daisy
    assert name == user.nickname  # they are both 'daisy' after the update

So :meth:`~gino.crud.CRUDModel.update` is the first GINO method we met so far
on model instance level. It accepts multiple keyword arguments, whose keys are
column names while values are the new value to update to. The following
:meth:`~gino.crud.UpdateRequest.apply` call makes the update happen in database.

.. note::

    GINO explicitly split the in-memory update and SQL update into two methods:
    :meth:`~gino.crud.CRUDModel.update` and
    :meth:`~gino.crud.UpdateRequest.apply`. :meth:`~gino.crud.CRUDModel.update`
    will update the in-memory model object and return an
    :class:`~gino.crud.UpdateRequest` object which contains all the
    modifications. A following :meth:`~gino.crud.UpdateRequest.apply` on
    :class:`~gino.crud.UpdateRequest` object will apply these recorded
    modifications to database by executing a compiled SQL.

.. tip::

    :class:`~gino.crud.UpdateRequest` object has another method named
    :meth:`~gino.crud.UpdateRequest.update` which works the same as the one
    on model object, just that it combines the new modifications together with
    the ones already recorded in current :class:`~gino.crud.UpdateRequest`
    object, and it returns the same :class:`~gino.crud.UpdateRequest` object.
    That means, you can chain the updates and end up with one
    :meth:`~gino.crud.UpdateRequest.apply`, or make use of the
    :class:`~gino.crud.UpdateRequest` object to combine several updates in a
    batch.

:meth:`~gino.crud.CRUDModel.update` on model object affects only the row
represented by the object. If you want to do update with wider condition, you
can use the :meth:`~gino.crud.CRUDModel.update` on model class level, with a
bit difference::

    await User.update.values(nickname='Founding Member ' + User.nickname).where(
        User.id < 10).gino.status()
    # SQL (parameter: 'Founding Member ', 10):
    # UPDATE users SET nickname=($1 || users.nickname) WHERE users.id < $2

    name = await User.select('nickname').where(
        User.id == 1).gino.scalar()
    print(name)  # Founding Member fantix

There is no :class:`~gino.crud.UpdateRequest` here, everything is again
SQLAlchemy clause, its
`documentation <https://docs.sqlalchemy.org/en/latest/core/dml.html>`_ here for
your reference.


Delete
^^^^^^

At last. Deleting is similar to updating, but way simpler. ::


    user = await User.create(nickname='fantix')
    await user.delete()
    # SQL (parameter: 1):
    # DELETE FROM users WHERE users.id = $1
    print(await User.get(user.id))  # None

.. hint::

    Remember the model object is in memory? In the last :func:`print`
    statement, even though the row is already deleted in database, the object
    ``user`` still exists with its values untouched.

Or mass deletion (never forget the where clause, unless you want to truncate
the whole table!!)::

    await User.delete.where(User.id > 10).gino.status()
    # SQL (parameter: 10):
    # DELETE FROM users WHERE users.id > $1


With basic :doc:`crud`, you can already make some amazing stuff with GINO. This
tutorial ends here, please find out more in detail from the rest of this
documentation, and have fun hacking!
