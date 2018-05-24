:orphan:

JSON Property
=============

PostgreSQL started to support native JSON type since 9.2, and became more
feature complete in 9.4. JSON is ideal to store varying key-value data. GINO
offers objective support for this scenario, requiring PostgreSQL 9.5 for now.

.. code-block:: python

   from gino import Gino

   db = Gino()

   class User(db.Model):
       __tablename__ = 'users'

       id = db.Column(db.Integer(), primary_key=True)
       profile = db.Column(db.JSONB())
       nickname = db.StringProperty(default='noname')
       age = db.IntegerProperty()

``nickname`` and ``age`` look just like normal columns, but they are actually
key-value pairs in the ``profile`` column. ``profile`` is the default column
name for JSON properties, you can specify a different name by offering the
argument ``column_name`` when defining a JSON property. Actually multiple JSON
columns are allowed, storing different JSON properties as needed. Also, both
``JSON`` and ``JSONB`` can be used, depending on your choice. For example:

.. code-block:: python

   from gino import Gino

   db = Gino()

   class Article(db.Model):
       __tablename__ = 'articles'

       id = db.Column(db.Integer(), primary_key=True)

       profile = db.Column(db.JSONB())
       author = db.StringProperty(default='noname')
       pub_index = db.IntegerProperty()

       values = db.Column(db.JSON())
       read_count = db.IntegerProperty(default=0, column_name='values')
       last_update = db.DateTimeProperty(column_name='values')

JSON properties work like normal columns too:

.. code-block:: python

   # Create with JSON property values
   u = await User.create(age=18)

   # Default value is immediately available
   u.nickname = 'Name: ' + u.nickname
   # identical to: u.update(nickname='Name' + u.nickname)

   # Updating only age, accept clause:
   await u.update(age=User.age + 2).apply()
