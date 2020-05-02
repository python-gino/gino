JSON Property
=============

GINO provides additional support to leverage native JSON type in the database as
flexible GINO model fields.

Quick Start
-----------

::

    from gino import Gino
    from sqlalchemy.dialects.postgresql import JSONB

    db = Gino()

    class User(db.Model):
        __tablename__ = "users"

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)
        profile = db.Column(JSONB, nullable=False, server_default="{}")

        age = db.IntegerProperty()
        birthday = db.DateTimeProperty()

The ``age`` and ``birthday`` are JSON properties stored in the ``profile`` column. You
may use them the same way as a normal GINO model field::

    u = await User.create(name="daisy", age=18)
    print(u.name, u.age)  # daisy 18

.. note::

    ``profile`` is the default column name for all JSON properties in a model. If you
    need a different column name for some JSON properties, you'll need to specify
    explicitly::

        audit_profile = db.Column(JSON, nullable=False, server_default="{}")

        access_log = db.ArrayProperty(prop_name="audit_profile")
        abnormal_detected = db.BooleanProperty(prop_name="audit_profile")

Using JSON properties in queries is supported::

    await User.query.where(User.age > 16).gino.all()

This is simply translated into a native JSON query like this:

.. code-block:: plpgsql

    SELECT users.id, users.name, users.profile
    FROM users
    WHERE CAST((users.profile ->> $1) AS INTEGER) > $2;  -- ('age', 16)

Datetime type is very much the same::

    from datetime import datetime

    await User.query.where(User.birthday > datetime(1990, 1, 1)).gino.all()

And the generated SQL:

.. code-block:: plpgsql

    SELECT users.id, users.name, users.profile
    FROM users
    WHERE CAST((users.profile ->> $1) AS TIMESTAMP WITHOUT TIME ZONE) > $2
    -- ('birthday', datetime.datetime(1990, 1, 1, 0, 0))

Here's a list of all the supported JSON properties:

+----------------------------+-----------------------------+-------------+---------------+
| JSON Property              | Python type                 | JSON type   | Database Type |
+============================+=============================+=============+===============+
| :class:`.StringProperty`   | :class:`str`                | ``string``  | ``text``      |
+----------------------------+-----------------------------+-------------+---------------+
| :class:`.IntegerProperty`  | :class:`int`                | ``number``  | ``int``       |
+----------------------------+-----------------------------+-------------+---------------+
| :class:`.BooleanProperty`  | :class:`bool`               | ``boolean`` | ``boolean``   |
+----------------------------+-----------------------------+-------------+---------------+
| :class:`.DateTimeProperty` | :class:`~datetime.datetime` | ``string``  | ``text``      |
+----------------------------+-----------------------------+-------------+---------------+
| :class:`.ObjectProperty`   | :class:`dict`               | ``object``  | JSON          |
+----------------------------+-----------------------------+-------------+---------------+
| :class:`.ArrayProperty`    | :class:`list`               | ``array``   | JSON          |
+----------------------------+-----------------------------+-------------+---------------+


Hooks
-----

JSON property provides 2 instance-level hooks to customize the data::

    class User(db.Model):
        __tablename__ = "users"

        id = db.Column(db.Integer, primary_key=True)
        profile = db.Column(JSONB, nullable=False, server_default="{}")

        age = db.IntegerProperty()

        @age.before_set
        def age(self, val):
            return val - 1

        @age.after_get
        def age(self, val):
            return val + 1

    u = await User.create(name="daisy", age=18)
    print(u.name, u.profile, u.age)  # daisy {'age': 17} 18

And 1 class-level hook to customize the SQLAlchemy expression of the property::

    class User(db.Model):
        __tablename__ = "users"

        id = db.Column(db.Integer, primary_key=True)
        profile = db.Column(JSONB, nullable=False, server_default="{}")

        height = db.JSONProperty()

        @height.expression
        def height(cls, exp):
            return exp.cast(db.Float)  # CAST(profile -> 'height' AS FLOAT)


Create Index on JSON Properties
-------------------------------

We'll need to use :meth:`~gino.declarative.declared_attr` to wait until the model class
is initialized. The rest is very much the same as defining a usual index::

    class User(db.Model):
        __tablename__ = "users"

        id = db.Column(db.Integer, primary_key=True)
        profile = db.Column(JSONB, nullable=False, server_default="{}")

        age = db.IntegerProperty()

        @db.declared_attr
        def age_idx(cls):
            return db.Index("age_idx", cls.age)

This will lead to the SQL below executed if you run ``db.gino.create_all()``:

.. code-block:: plpgsql

    CREATE INDEX age_idx ON users (CAST(profile ->> 'age' AS INTEGER));

.. warning::

    Alembic doesn't support auto-generating revisions for functional indexes yet. You'll
    need to manually edit the revision. Please follow `this issue
    <https://github.com/sqlalchemy/alembic/issues/676>`__ for updates.
