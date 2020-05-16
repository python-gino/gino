Use Alembic
===========

Alembic is a lightweight database migration tool for usage with the SQLAlchemy Database Toolkit for Python.
It’s also possible to use with GinoORM.

To add migrations to project first of all, add alembic as dependency:

.. code-block:: console

   $ pip install --user alembic

When you need to set up alembic for your project.

Prepare sample project. We will have a structure:


.. code-block:: console

    alembic_sample/
        my_app/
            models.py

Inside models.py define simple DB Model with Gino ORM:

.. code-block:: python

    from gino import Gino

    db = Gino()

        class User(db.Model):
            __tablename__ = 'users'

     id = db.Column(db.Integer(), primary_key=True)
     nickname = db.Column(db.Unicode(), default='noname')


Set up Alembic
^^^^^^^^^^^^^^

This will need to be done only once. Go to the main folder of your project ‘alembic_sample’ and run:

.. code-block:: console

    $ alembic init alembic


Alembic will create a bunch of files and folders in your project directory. One of them will be ``alembic.ini``.
Open ``alembic.ini`` (you can find it in the main project folder ``alembic_sample``). Now change property ‘sqlalchemy.url =’  with your DB credentials. Like this:

.. code-block:: ini

    sqlalchemy.url = postgres://{{username}}:{{password}}@{{address}}/{{db_name}}


Next go to folder alembic/ and open env.py file. Inside the env.py file you need to import the db object. In our case db object is ‘db’ from models modules. This is a variable that links to your Gino() instance.

Inside alembic/env.py:

.. code-block:: python

    from main_app.models import db


And change ``target_metadata =`` to:

.. code-block:: python

    target_metadata = db

That’s it. We finished setting up Alembic for a project.

.. note::

    All ``alembic`` commands must be run always from the folder that contains the ``alembic.ini`` file.


Create first migration revision
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Same commands you must run each time when you make some changes in DB Models and want to apply these changes to your DB Schema.

.. code-block:: console

    $ alembic revision -m "first migration" --autogenerate --head head

If you have any problems relative to package imports similar to this example:

.. code-block:: console

    File "alembic/env.py", line 7, in <module>
        from main_app.models import db
    ModuleNotFoundError: No module named 'main_app'

Add you package to PYTHONPATH, like this:

.. code-block:: console

    $ export PYTHONPATH=$PYTHONPATH:/full_path/to/alembic_sample


After the successful run of ``alembic revision`` in folder ``alembic/versions`` you will see a file with new migration.


Apply migration on DB
^^^^^^^^^^^^^^^^^^^^^

Now time to apply migration to DB. It will create tables based on you DB Models.

.. code-block:: console

    $ alembic upgrade head

Great. Now you apply your first migration. Congratulations!

Next time, when you will make any changes in DB models just do:

.. code-block:: console

    $ alembic revision -m "your migration description" --autogenerate --head head

And

.. code-block:: console

    alembic upgrade head


Full documentation about how to work with Alembic migrations, downgrades and other things - you can find in official docs https://alembic.sqlalchemy.org
