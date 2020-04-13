Build a FastAPI Server
======================

In this tutorial, we'll build a production-ready FastAPI_ server together.
The full functional example is available `here
<https://github.com/python-gino/gino-starlette/tree/master/examples/prod_fastapi_demo>`_.

.. _FastAPI: https://fastapi.tiangolo.com/


Start a New Project
-------------------

Instead of pip, let's use the shiny Poetry_ to manage our project. Follow the link to
`install Poetry <https://python-poetry.org/docs/#installation>`_, and create our new
project in an empty directory:


.. code-block:: console

    $ mkdir gino-fastapi-demo
    $ cd gino-fastapi-demo
    $ git init
    $ poetry init

Then follow the Poetry_ guide to finish the initialization - you may say "no" to the
interactive dependency creation, because we will add them manually. It is okay to use
the default values in the other steps of the guide, and make sure the package name
remains ``gino-fastapi-demo``.

.. _Poetry: https://python-poetry.org/


Add Dependencies
----------------

FastAPI_ is built on top of the Starlette_ framework, so we shall use the `GINO
extension for Starlette <https://github.com/python-gino/gino-starlette>`_. Simply run:

.. code-block:: console

    $ poetry add 'gino[starlette]@^1.0'

.. note::

    Before the final GINO 1.0 is released, please use 1.0rc3 for now:

    .. code-block:: console

        $ poetry add 'gino[starlette]@^1.0rc3' --allow-prereleases

Then let's add FastAPI_, together with the lightning-fast ASGI_ server uvicorn_, and
Gunicorn_ as a production application server:

.. code-block:: console

    $ poetry add fastapi uvicorn gunicorn

For database migration, we'll use Alembic_. Because it uses normal DB-API_, we need
psycopg_ here too:

.. code-block:: console

    $ poetry add alembic psycopg2

At last, let's add pytest_ in the development environment for testing:

.. code-block:: console

    $ poetry add -D pytest

.. hint::

    With the steps above, Poetry_ will automatically create a virtualenv_ for you
    behind the scene, and all the dependencies are installed there. We will assume
    using this for the rest of the tutorial. But you're free to create your own
    virtualenv_, and Poetry_ will honor it when it's activated.

That's all, this is my ``pyproject.toml`` created by Poetry_:

.. code-block:: toml

    [tool.poetry]
    name = "gino-fastapi-demo"
    version = "0.1.0"
    description = ""
    authors = ["Fantix King <fantix.king@gmail.com>"]

    [tool.poetry.dependencies]
    python = "^3.8"
    gino = {version = "^1.0", extras = ["starlette"]}
    fastapi = "^0.54.1"
    uvicorn = "^0.11.3"
    gunicorn = "^20.0.4"
    alembic = "^1.4.2"
    psycopg2 = "^2.8.5"

    [tool.poetry.dev-dependencies]
    pytest = "^5.4.1"

    [build-system]
    requires = ["poetry>=0.12"]
    build-backend = "poetry.masonry.api"

.. image:: ../images/gino-fastapi-poetry.svg
   :align: right

And there's also an auto-generated ``poetry.lock`` file with the frozen versions. The
directory layout should look like the diagram on the right. Now let's add the two files
to the Git repository (we will skip showing this in future steps):

.. code-block:: console

    $ git add pyproject.toml poetry.lock
    $ git commit -m 'add project dependencies'

Our application stack will look like this:

.. image:: ../images/gino-fastapi.svg
   :align: center

.. _Starlette: https://www.starlette.io/
.. _ASGI: https://asgi.readthedocs.io/
.. _uvicorn: https://www.uvicorn.org/
.. _Gunicorn: https://gunicorn.org/
.. _Alembic: https://alembic.sqlalchemy.org/
.. _DB-API: https://www.python.org/dev/peps/pep-0249/
.. _psycopg: https://www.psycopg.org/
.. _pytest: https://docs.pytest.org/
.. _virtualenv: https://virtualenv.pypa.io/


Write a Simple Server
---------------------

Now let's write some Python code.

We'll create an extra ``src`` directory to include all the Python files, as demonstrated
in the diagram below. This is known as the "`src layout
<https://hynek.me/articles/testing-packaging/>`_" providing a cleaner hierarchy.

.. image:: ../images/gino-fastapi-src.svg
   :align: right

The root Python package of our project is named as ``gino_fastapi_demo``, under which we
will create two Python modules:

* ``asgi`` as the ASGI entry point - we'll feed it to the ASGI server
* ``main`` to initialize our server

Here's ``main.py``::

    from fastapi import FastAPI

    def get_app():
        app = FastAPI(title="GINO FastAPI Demo")
        return app

And we'll simply instantiate our application in ``asgi.py``::

    from .main import get_app

    app = get_app()

Then run ``poetry install`` to link our Python package into the ``PYTHONPATH`` in
development mode. We'll be able to start a uvicorn development server after that:

.. code-block:: console

    $ poetry install
    $ poetry run uvicorn gino_fastapi_demo.asgi:app --reload
    INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
    INFO:     Started reloader process [53010]
    INFO:     Started server process [53015]
    INFO:     Waiting for application startup.
    INFO:     Application startup complete.

The ``--reload`` option enables uvicorn to automatically reload the server for us when
the Python source code is updated. Now access http://127.0.0.1:8000/docs to see the
Swagger UI of our new FastAPI server.

.. hint::

    As mentioned previously, if you're in your own virtualenv, the command ``poetry run
    uvicorn`` can be simplified as just ``uvicorn``.

    ``poetry run`` is a convenient shortcut to run the following command in the
    virtualenv managed by Poetry.
