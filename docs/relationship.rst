=============
Relationships
=============

As for now (April 2018) GINO has no full support for relationships. For one
thing, we are still trying to find a decent way implementing relationships, for
another, we insist explicit code style in asynchronous programming and that
conflicts with some usual ORM relationship patterns. Still, GINO doesn't stop
you from using relationships in the database through foreign keys or whatever
magic, and gradually provides more features to support doing so.


Model Loader
------------

The Model Loader is the magic behind GINO CRUD to translate database rows into
model objects. Through CRUD, Model Loaders are assembled internally for you,
you can still use it directly. For example, an ordinary query that returns rows
may look like this::

    query = db.select([User])
    rows = await query.gino.all()

In order to load rows into ``User`` objects, you can provide an execution
option ``loader`` with a new :class:`~gino.loader.ModelLoader` instance::

    from gino.loader import ModelLoader

    query = db.select([User])
    query = query.execution_options(loader=ModelLoader(User))
    users = await query.gino.all()

The :class:`~gino.loader.ModelLoader` would then load each database row into a
``User`` object. As this is frequently used, GINO made it a shortcut::

    query = db.select([User])
    query = query.execution_options(loader=User.load())
    users = await query.gino.all()

And another shortcut::

    query = db.select([User])
    query = query.execution_options(loader=User)
    users = await query.gino.all()

.. tip::

    ``User`` as ``loader`` is transformed into ``ModelLoader(User)`` by
    :meth:`Loader.get() <gino.loader.Loader.get>`, explained later in "Loader
    Expression".

And again::

    query = db.select([User])
    users = await query.gino.load(User).all()

This is identical to the normal CRUD query::

    users = await User.query.gino.all()


Loader Expression
-----------------

So Loaders are actually row post-processors, they define how the database rows
should be processed and returned. Other than :class:`~gino.loader.ModelLoader`,
there're also other loaders that could turn the database rows into different
results like based on your definition. GINO provides the Loader Expression
feature for you to easily assemble complex loaders.


.. tip::

    This is less relevant to relationships, please skip to the next section if
    it's not helpful for you.

Here is an example using all loaders at once::

    uid, user, sep, cols = await db.select([User]).gino.load(
        (
            User.id,
            User,
            '|',
            lambda row, ctx: len(row),
        )
    ).first()

Let's check this piece by piece. Overall, the argument of
:meth:`~gino.api.GinoExecutor.load` is a tuple. This is interpreted into a
:class:`~gino.loader.TupleLoader`, with each item of the tuple interpreted as a
Loader Expression recursively. That means, it is possible to nest tuples. The
result of a :class:`~gino.loader.TupleLoader` is a tuple.

:class:`~sqlalchemy.schema.Column` in Loader Expressions are interpreted as
:class:`~gino.loader.ColumnLoader`. It simply outputs the value of the given
column in the database row. It is your responsibility to select the column in
the query. Please note, :class:`~gino.loader.ColumnLoader` uses the given
column as index to look for the value, not the name of the column. This is a
SQLAlchemy feature to support selecting multiple columns with the same name
from different tables in the same query, especially for ORM. So if you are
using raw textual SQL and wishing to use :class:`~gino.loader.ColumnLoader`,
you'll have to declare columns for the query::

    now = db.Column('time', db.DateTime())
    result = await db.first(db.text(
        'SELECT now() AT TIME ZONE \'UTC\''
    ).columns(
        now,
    ).gino.load(
        ('now:', now)
    ).first()
    print(result)  # now: 2018-04-08 08:23:02.431847

Let's get back to previous example. The second item in the tuple is a GINO
model class. As we've presented previously, it is interpreted into a
:class:`~gino.loader.ModelLoader`. By default, it loads the values of all the
columns of the give model, and create a new model instance with the values.

.. tip::

    For a complex loader expression, the same row is given to all loaders, so
    it doesn't matter ``User.id`` is already used before the model loader.

The last item in the tuple is a callable, it will be called for each row with
two arguments: the first argument is the row itself, while the second is a
contextual value provided by outer loader, we'll get to that later. Similar to
:func:`map`, the return value of the call will be the loaded result.

At last, if none of the above types matches a Loader Expression, it will be
treated as is. Like the ``'|'`` separator, it will show up as the third item
in every result returned by the query.


Many-to-One Relationship
------------------------

A classic many-to-one relationship is also known as referencing - the model on
the "many" end keeps a single reference to the model on the "one" end. Although
GINO does not enforce it, usually people use a foreign key for the reference::

    class Parent(db.Model):
        __tablename__ = 'parents'
        id = db.Column(db.Integer, primary_key=True)

    class Child(db.Model):
        __tablename__ = 'children'
        id = db.Column(db.Integer, primary_key=True)
        parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'))

So every child has a single parent (or no parent at all), while one parent may
have multiple children. GINO provides an easy way to load children with their
parents::

    async for child in Child.load(parent=Parent).gino.iterate():
        print(f'Parent of {child.id} is {child.parent.id}')

As you may have noticed, ``Child.load`` is exactly the shortcut to create
:class:`~gino.loader.ModelLoader` in the very first example. With some
additional keyword arguments, ``Child.load(parent=Parent)`` is still a
:class:`~gino.loader.ModelLoader` for ``Child``, the model loader is at the
same time a **query builder**. It is identical to do this::

    async for child in Child.load(parent=Parent).query.gino.iterate():
        print(f'Parent of {child.id} is {child.parent.id}')

The :attr:`~gino.loader.Loader.query` dynamically generates a SQLAlchemy query
based on the knowledge of the loader, and set the loader as execution option at
the same time. The :class:`~gino.loader.Loader` simply forwarded unknown
attributes to its :attr:`~gino.loader.Loader.query`, that's why ``.query`` can
be omitted.

For :class:`~gino.loader.ModelLoader`, all keyword arguments are interpreted as
subloaders, their results will be set to the attributes of the result model
under the corresponding keys using :func:`setattr`. For example, ``Parent`` is
interpreted as ``ModelLoader(Parent)`` which loads ``Parent`` instances, and
``Parent`` instances are set as the ``parent`` attribute of the outer ``Child``
instance.

.. warning::

    If multiple children references the same parent, then each child owns a
    unique parent instance with identical values.

.. tip::

    You don't have to define ``parent`` attribute on ``Child``. But if you do,
    you gain the ability to customize how parent is stored or retrieved. For
    example, let's store the parent instance as ``_parent``::

        class Child(db.Model):
            __tablename__ = 'children'
            id = db.Column(db.Integer, primary_key=True)
            parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'))
            _parent = None

            @property
            def parent(self):
                return self._parent

            @parent.setter
            def parent(self, value):
                self._parent = value

The query builder works recursively. For :class:`~gino.loader.ModelLoader`, it
uses ``LEFT OUTER JOIN`` to connect the ``FROM`` clauses, in order to achieve
many-to-one scenario. The ``ON`` clause is determined automatically by foreign
keys. You can also customize the ``ON`` clause in case there is no foreign key
(a promise is a promise)::

    loader = Child.load(parent=Parent.on(Child.parent_id == Parent.id))
    async for child in loader.query.gino.iterate():
        print(f'Parent of {child.id} is {child.parent.id}')

And subloaders can be nested::

    subloader = Child.load(parent=Parent.on(Child.parent_id == Parent.id))
    loader = Grandson.load(parent=subloader.on(Grandson.parent_id == Child.id))

By now, GINO supports only loading many-to-one joined query. To modify a
relationship, just modify the reference column values.


Self Referencing
----------------

.. warning::

    Experimental feature.

Self referencing is usually used to create a tree-like structure. For example::

    class Category(db.Model):
        __tablename__ = 'categories'
        id = db.Column(db.Integer, primary_key=True)
        parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'))

In order to load leaf categories with their parents, an alias is needed::

    Parent = Category.alias()

Then the query would be something like this::

    parents = db.select([Category.parent_id])
    query = Category.load(parent=Parent.on(
        Category.parent_id == Parent.id
    )).where(
        ~Category.id.in_(db.select([Category.alias().parent_id]))
    )
    async for c in query.gino.iterate():
        print(f'Leaf: {c.id}, Parent: {c.parent.id}')

The generated SQL looks like this:

.. code-block:: SQL

    SELECT categories.id, categories.parent_id, categories_1.id, categories_1.parent_id
      FROM categories LEFT OUTER JOIN categories AS categories_1
        ON categories.parent_id = categories_1.id
     WHERE categories.id NOT IN (
               SELECT categories_2.parent_id
                 FROM categories AS categories_2
           )


Other Relationships
-------------------

GINO 0.7.4 introduced an experimental distinct feature to reduce a result set
with loaders, combining rows under specified conditions. This made it possible
to build one-to-many relationships. Using the same parent-child example above,
we could load distinct parents with all their children::

    class Parent(db.Model):
        __tablename__ = 'parents'
        id = db.Column(db.Integer, primary_key=True)

        def __init__(self, **kw):
            super().__init__(**kw)
            self._children = set()

        @property
        def children(self):
            return self._children

        @children.setter
        def add_child(self, child):
            self._children.add(child)


    class Child(db.Model):
        __tablename__ = 'children'
        id = db.Column(db.Integer, primary_key=True)
        parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'))


    query = Child.outerjoin(Parent).select()
    parents = await query.gino.load(
        Parent.distinct(Parent.id).load(add_child=Child)).all()

Here the query is still child outer-joining parent, but the loader is loading
parent instances with distinct IDs only, while storing all their children
through the ``add_child`` setter property. In detail for each row, a parent
instance is firstly loaded if no parent instance with the same ID was loaded
previously, or the same parent instance will be reused. Then a child instance
is loaded from the same row, and fed to the possibly reused parent instance by
``parent.add_child = new_child``.

Distinct loaders can be nested to load hierarchical data, but it cannot be used
as a query builder to automatically generate queries.

GINO provides no additional support for one-to-one relationship - the user
should make sure that the query produces rows of distinct instance pairs, and
load them with regular GINO model loaders. When in doubt, the distinct feature
can be used on both sides, but you'll have to manually deal with the conflict
if more than one related instances are found. For example, we could keep only
the last child for each parent::

    class Parent(db.Model):
        __tablename__ = 'parents'
        id = db.Column(db.Integer, primary_key=True)

        def __init__(self, **kw):
            super().__init__(**kw)
            self._child = None

        @property
        def child(self):
            return self._child

        @child.setter
        def child(self, child):
            self._child = child


    class Child(db.Model):
        __tablename__ = 'children'
        id = db.Column(db.Integer, primary_key=True)
        parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'))


    query = Child.outerjoin(Parent).select()
    parents = await query.gino.load(
        Parent.distinct(Parent.id).load(child=Child.distinct(Child.id))).all()


Similarly, you can build many-to-many relationships in the same way::

    class Parent(db.Model):
        __tablename__ = 'parents'
        id = db.Column(db.Integer, primary_key=True)

        def __init__(self, **kw):
            super().__init__(**kw)
            self._children = set()

        @property
        def children(self):
            return self._children

        @children.setter
        def add_child(self, child):
            self._children.add(child)
            child._parents.add(self)


    class Child(db.Model):
        __tablename__ = 'children'
        id = db.Column(db.Integer, primary_key=True)

        def __init__(self, **kw):
            super().__init__(**kw)
            self._parents = set()

        @property
        def parents(self):
            return self._parents


    class ParentXChild(db.Model):
        __tablename__ = 'parents_x_children'

        parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'))
        child_id = db.Column(db.Integer, db.ForeignKey('children.id'))


    query = Parent.outerjoin(ParentXChild).outerjoin(Child).select()
    parents = await query.gino.load(
        Parent.distinct(Parent.id).load(add_child=Child.distinct(Child.id))).all()

Likewise, there is for now no way to modify the relationships automatically,
you'll have to manually create, delete or modify ``ParentXChild`` instances.
