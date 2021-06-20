Frequently Asked Questions
==========================

SQLAlchemy 1.4 supports asyncio, what will GINO be?
---------------------------------------------------

Starting from 1.4, SQLAlchemy will `support asyncio
<https://docs.sqlalchemy.org/en/14/changelog/migration_14.html#asynchronous-io-support-for-core-and-orm>`__.
This is a great news to the SQLAlchemy-based ORMs including GINO, because the users will
have one more option, and many GINO hacks can be eventually cleaned up. SQLAlchemy
achieved both sync and async API with the same code base by encapsulating the use of
`greenlet <https://greenlet.readthedocs.io/en/latest/>`__. As an "async" user, you don't
need to worry about its internals in most cases, it's fine to just use its async APIs.
Both SQLAlchemy Core and ORM will be async-compatible, but some ORM features that
involve implicit database accesses are disallowed.

Given such news, GINO no longer has to maintain its own asyncpg dialect for SQLAlchemy
in future versions (yay!). Still, GINO will focus on the differences and keep a
compatible API. To list some of the different/future features:

* Contextual Connections (see :doc:`../explanation/engine`)
* SQLAlchemy Core-based CRUD models
* The GINO Loader system
* Async MySQL support
* Typing support :sup:`NEW`
* `Trio <https://trio.readthedocs.io/en/stable/>`__ support :sup:`NEW`
* Execution performance :sup:`NEW`

As SQLAlchemy async support is considered in Alpha level, GINO will include SQLAlchemy
1.4 support in GINO 2.0.0-alpha.x releases, while the current GINO 1.0.x and 1.1.x will
remain on SQLAlchemy 1.3. GINO 1.x will receive bug fixes and security updates until
both SQLAlchemy async support and GINO 2.x are stabilized.


ORM or not ORM?
---------------

GINO does perform the Object-Relational Mapping work under the
`Data Mapper Pattern <https://en.wikipedia.org/wiki/Data_mapper_pattern>`_, but
it is just not a traditional ORM. The Objects in GINO are completely stateless
from database - they are pure plain Python objects in memory. Changing their
attribute values does not make them "dirty" - or in a different way of thinking
they are always "dirty". Any access to database must be explicitly executed.
Using GINO is more like making up SQL clauses with Models and Objects,
executing them to make changes in database, or loading data from database and
wrapping the results with Objects again. Objects are just row data containers,
you are still dealing with SQL which is represented by Models and SQLAlchemy
core grammars. Besides GINO can be used in a completely `non-ORM way
<schema.html#gino-core>`__.


Can I use features of SQLAlchemy ORM?
-------------------------------------

SQLAlchemy has `two parts <https://docs.sqlalchemy.org/en/13/>`__:

* SQLAlchemy Core
* SQLAlchemy ORM

GINO is built on top of SQLAlchemy Core, so SQLAlchemy ORM won't work in GINO.


How to join?
------------

GINO invented none about making up queries, everything for that is inherited
from SQLAlchemy. Therefore you just need to know `how to write join in
SQLAlchemy <https://docs.sqlalchemy.org/en/latest/core/tutorial.html#using-joins>`_.
Especially, `Ádám <https://github.com/brncsk>`_ made some amazing upgrades in
GINO `#113 <https://github.com/python-gino/gino/pull/113>`_ to make join easier, so
that you can use model classes directly as if they are tables in joining::

    results = await User.join(Book).select().gino.all()


How to connect to database through SSL?
---------------------------------------

It depends on the dialect and database driver. For asyncpg, keyword arguments
on :func:`asyncpg.connect() <asyncpg.connection.connect>` are directly
available on :func:`~gino.create_engine` or :meth:`db.set_bind()
<gino.api.Gino.set_bind>`. Therefore, enabling SSL is rather easy::

    engine = await gino.create_engine(..., ssl=True)


What is aiocontextvars and what does it do?
-------------------------------------------

It is a partial backport of the new built-in module `contextvars
<https://docs.python.org/3.7/library/contextvars.html>`_ introduced in Python
3.7. In Python 3.6, ``aiocontextvars`` patches ``loop.create_task()``
to copy context from caller as a workaround to simulate the same behavior. This
is also under discussion in upstream backport project, please read more here:
https://github.com/MagicStack/contextvars/issues/2

If you are using Python 3.7, then ``aiocontextvars`` does nothing at all.

.. note::

    This answer is for GINO 0.8 and later, please check earlier versions of
    this documentation if you are using GINO 0.7.


How to define relationships?
----------------------------

GINO 1.0 or lower doesn't provide relationship definition feature found in typical ORMs.
However, you could always manually define your tables, design your queries and load the
results explicitly in GINO. Please see :doc:`loaders` for more information.


How to define index with multiple columns?
------------------------------------------

::

    class User(db.Model):
        __tablename__ = 'users'

        first_name = db.Column(db.Unicode())
        last_name = db.Column(db.Unicode())

        _name_idx = db.Index('index_on_name', 'first_name', 'last_name')

The ``_name_idx`` is not used.


Is there a django admin interface for GINO?
-------------------------------------------

Not quite yet, please follow `this discussion
<https://github.com/python-gino/gino/issues/260>`__.


How to use multiple databases for different users on the fly?
-------------------------------------------------------------

GINO models are linked to a :class:`~gino.api.Gino` instance, while
:class:`~gino.api.Gino` has an optional property ``bind`` to hold a
:class:`~gino.engine.GinoEngine` instance. So when you are executing::

    user = await User.get(request.user_id)

The ``bind`` is implicitly used to execute the query.

In order to use multiple databases, you would need multiple
:class:`~gino.engine.GinoEngine` instances. Here's a full example using FastAPI with
lazy engine creation::

    from asyncio import Future
    from contextvars import ContextVar

    from fastapi import FastAPI, Request
    from gino import create_engine
    from gino.ext.starlette import Gino

    engines = {}
    dbname = ContextVar("dbname")


    class ContextualGino(Gino):
        @property
        def bind(self):
            e = engines.get(dbname.get(""))
            if e and e.done():
                return e.result()
            else:
                return self._bind

        @bind.setter
        def bind(self, val):
            self._bind = val


    app = FastAPI()
    db = ContextualGino(app)


    @app.middleware("http")
    async def lazy_engines(request: Request, call_next):
        name = request.query_params.get("db", "postgres")
        fut = engines.get(name)
        if fut is None:
            fut = engines[name] = Future()
            try:
                engine = await create_engine("postgresql://localhost/" + name)
            except Exception as e:
                fut.set_exception(e)
                del engines[name]
                raise
            else:
                fut.set_result(engine)
        await fut
        dbname.set(name)
        return await call_next(request)


    @app.get("/")
    async def get():
        return dict(dbname=await db.scalar("SELECT current_database()"))


How to load complex query results?
----------------------------------

The API doc of :mod:`gino.loader` explains the available loaders, and there're a few
examples in :doc:`loaders` too.

Below is an example with a joined result to load both a GINO model and an integer at the
same time, using a :class:`~gino.loader.TupleLoader` with two sub-loaders -
:class:`~gino.loader.ModelLoader` and :class:`~gino.loader.ColumnLoader`::

    import asyncio
    import random
    import string

    import gino
    from gino.loader import ColumnLoader

    db = gino.Gino()


    class User(db.Model):
        __tablename__ = 'users'

        id = db.Column(db.Integer(), primary_key=True)
        name = db.Column(db.Unicode())


    class Visit(db.Model):
        __tablename__ = 'visits'

        id = db.Column(db.Integer(), primary_key=True)
        time = db.Column(db.DateTime(), server_default='now()')
        user_id = db.Column(db.ForeignKey('users.id'))


    async def main():
        async with db.with_bind('postgresql://localhost/gino'):
            await db.gino.create_all()

            for i in range(random.randint(5, 10)):
                u = await User.create(
                    name=''.join(random.choices(string.ascii_letters, k=10)))
                for v in range(random.randint(10, 20)):
                    await Visit.create(user_id=u.id)

            visits = db.func.count(Visit.id)
            q = db.select([
                User,
                visits,
            ]).select_from(
                User.outerjoin(Visit)
            ).group_by(
                *User,
            ).gino.load((User, ColumnLoader(visits)))
            async with db.transaction():
                async for user, visits in q.iterate():
                    print(user.name, visits)

            await db.gino.drop_all()


    asyncio.run(main())

Be ware of the :class:`tuple` in ``.gino.load((...))``.



How to do bulk or batch insert / update?
-----------------------------------------

For a simple example, take a model that has one field, "name." In your application you
have a list of names you would like to add to the database::

    new_names = ["Austin", "Ali", "Jeff", "Marissa"]

To quickly insert the names in one query, first construct a dict with the
``{"model_key": "value"}`` format::

    new_names_dict = [dict(name=new_name) for new_name in new_names]
    >> [{'name': 'Austin'}, {'name': 'Ali'}, {'name': 'Jeff'}, {'name': 'Marissa'}]

Finally, run an insert statement on the model::

    await User.insert().gino.all(new_names_dict)


How to print the executed SQL?
------------------------------

GINO uses the same approach from SQLAlchemy: ``create_engine(..., echo=True)``.
(Or ``db.set_bind(..., echo=True)``) Please see also `here
<https://docs.sqlalchemy.org/en/13/core/engines.html#sqlalchemy.create_engine.params.echo>`__.

If you use any extension, you can also set that in config, by `db_echo` or `DB_ECHO`.


How to run ``EXISTS`` SQL?
--------------------------

::

    await db.scalar(db.exists().where(User.email == email).select())


How to work with Alembic?
-------------------------

The fact that :class:`~gino.api.Gino` is a :class:`~sqlalchemy.schema.MetaData` is the
key to use Alembic. Just import and set ``target_metadata = db`` in Alembic ``env.py``
will do. See :doc:`alembic` for more details.


How to join the same table twice?
---------------------------------

This is the same pattern as described in SQLAlchemy :ref:`self_referential`, where you
have a table with "a foreign key reference to itself", or join the same table more than
once, "to represent hierarchical data in flat tables." We'd need to use
:func:`~gino.crud.CRUDModel.alias`, for example::

    class User(db.Model):
        __tablename__ = "users"

        id = db.Column(db.Integer, primary_key=True)
        parent_id = db.Column(db.ForeignKey("users.id"))

    Parent = User.alias()
    query = User.outerjoin(Parent, User.parent_id == Parent.id).select()
    users = await query.gino.load(User.load(parent=Parent)).all()


.. _raw-sql:

How to execute raw SQL with parameters?
---------------------------------------

Wrap the SQL with :func:`~sqlalchemy.sql.expression.text`, and use keyword arguments::

    query = db.text('SELECT * FROM users WHERE id = :id_val')
    row = await db.first(query, id_val=1)

You may even load the rows into model instances::

    query = query.execution_options(loader=User)
    user = await db.first(query, id_val=1)


Gino engine is not initialized?
-------------------------------

GINO models are linked to a :class:`~gino.api.Gino` instance, while
:class:`~gino.api.Gino` has an optional property ``bind`` to hold a
:class:`~gino.engine.GinoEngine` instance. So when you are executing::

    user = await User.get(request.user_id)

The ``bind`` is implicitly used to execute the query. If ``bind`` is not set before
this, you'll see this error:

.. code-block:: text

    gino.exceptions.UninitializedError: Gino engine is not initialized.

You could use either:

* Call :meth:`~gino.api.Gino.set_bind` or :meth:`~gino.api.Gino.with_bind` to set the
  bind on the :class:`~gino.api.Gino` instance.
* Use one of the Web framework extensions to set the bind for you in usually the server
  start-up hook.
* Use explicit ``bind`` for each execution, for example::

      engine = await create_engine("...")
      # ...
      user = await User.get(request.user_id, bind=engine)


How can I do SQL xxxx in GINO?
------------------------------

GINO uses `SQLAlchemy Core <https://docs.sqlalchemy.org/en/13/core/>`__ queries, so
please check its documentation on how to build queries. The GINO models are simply
wrappers of SQLAlchemy :class:`~sqlalchemy.schema.Table` instances, and the column
attributes on GINO model classes are just SQLAlchemy :class:`~sqlalchemy.schema.Column`
instances, you can use them in building your SQLAlchemy Core queries.

Alternatively, you could always execute the raw SQL directly, see :ref:`raw-sql` above.
