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
