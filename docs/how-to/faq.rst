Frequently Asked Questions
==========================

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
core grammars. Besides GINO can be used in a completely non-ORM way.


How to join?
------------

GINO invented none about making up queries, everything for that is inherited
from SQLAlchemy. Therefore you just need to know `how to write join in
SQLAlchemy <https://docs.sqlalchemy.org/en/latest/core/tutorial.html#using-joins>`_.
Especially, `Ádám <https://github.com/brncsk>`_ made some amazing upgrades in
GINO `#113 <https://github.com/fantix/gino/pull/113>`_ to make join easier, so
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
3.7. In Python 3.5 and 3.6, ``aiocontextvars`` patches ``loop.create_task()``
to copy context from caller as a workaround to simulate the same behavior. This
is also under discussion in upstream backport project, please read more here:
https://github.com/MagicStack/contextvars/issues/2

If you are using Python 3.7, then ``aiocontextvars`` does nothing at all.

.. note::

    This answer is for GINO 0.8 and later, please check earlier versions of
    this documentation if you are using GINO 0.7.
