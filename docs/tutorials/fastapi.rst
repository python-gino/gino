Build a FastAPI Server
======================

In this tutorial, we'll build a production-ready FastAPI_ server together.
The full functional example is available `here
<https://github.com/python-gino/gino-starlette/tree/master/examples/prod_fastapi_demo>`_.

Our application stack will look like this:

.. image:: ../images/gino-fastapi.svg
   :align: center


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

Then let's add FastAPI_, together with the lightning-fast ASGI_ server Uvicorn_, and
Gunicorn_ as a production application server:

.. code-block:: console

    $ poetry add fastapi uvicorn gunicorn

For database migration, we'll use Alembic_. Because it uses normal DB-API_, we need
psycopg_ here too:

.. code-block:: console

    $ poetry add alembic psycopg2

At last, let's add pytest_ in the development environment for testing. We also want to
add the requests_ library to use the Starlette_ |TestClient|_:

.. code-block:: console

    $ poetry add -D pytest requests

.. hint::

    With the steps above, Poetry_ will automatically create a virtualenv_ for you
    behind the scene, and all the dependencies are installed there. We will assume
    using this for the rest of the tutorial. But you're free to create your own
    virtualenv_, and Poetry_ will honor it when it's activated.

That's all, this is my ``pyproject.toml`` created by Poetry_, yours should look similar:

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
    requests = "^2.23.0"

    [build-system]
    requires = ["poetry>=0.12"]
    build-backend = "poetry.masonry.api"

.. image:: ../images/gino-fastapi-poetry.svg
   :align: right

And there's also an auto-generated ``poetry.lock`` file with the frozen versions. The
directory layout should look like the diagram on the right. Now let's add the two files
to the Git repository (we will skip showing these git operations in future steps):

.. code-block:: console

    $ git add pyproject.toml poetry.lock
    $ git commit -m 'add project dependencies'

.. _Starlette: https://www.starlette.io/
.. _ASGI: https://asgi.readthedocs.io/
.. _Uvicorn: https://www.uvicorn.org/
.. _Gunicorn: https://gunicorn.org/
.. _Alembic: https://alembic.sqlalchemy.org/
.. _DB-API: https://www.python.org/dev/peps/pep-0249/
.. _psycopg: https://www.psycopg.org/
.. _pytest: https://docs.pytest.org/
.. _virtualenv: https://virtualenv.pypa.io/
.. _requests: https://requests.readthedocs.io/


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
development mode. We'll be able to start a Uvicorn development server after that:

.. code-block:: console

    $ poetry install
    $ poetry run uvicorn gino_fastapi_demo.asgi:app --reload
    INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
    INFO:     Started reloader process [53010]
    INFO:     Started server process [53015]
    INFO:     Waiting for application startup.
    INFO:     Application startup complete.

The ``--reload`` option enables Uvicorn to automatically reload the server for us when
the Python source code is updated. Now access http://127.0.0.1:8000/docs to see the
Swagger UI of our new FastAPI server.

.. hint::

    As mentioned previously, if you're in your own virtualenv, the command ``poetry run
    uvicorn`` can be simplified as just ``uvicorn``.

    ``poetry run`` is a convenient shortcut to run the following command in the
    virtualenv managed by Poetry.


Add GINO Extension
------------------

.. image:: ../images/gino-fastapi-config.svg
   :align: right

Now let's add GINO to our server.

First of all, we need a way to configure the database. In this tutorial, we'll use the
`configuration system <https://www.starlette.io/config/>`_ from Starlette_.
Add ``src/gino_fastapi_demo/config.py`` as follows::

    from sqlalchemy.engine.url import URL, make_url
    from starlette.config import Config
    from starlette.datastructures import Secret

    config = Config(".env")

    DB_DRIVER = config("DB_DRIVER", default="postgresql")
    DB_HOST = config("DB_HOST", default=None)
    DB_PORT = config("DB_PORT", cast=int, default=None)
    DB_USER = config("DB_USER", default=None)
    DB_PASSWORD = config("DB_PASSWORD", cast=Secret, default=None)
    DB_DATABASE = config("DB_DATABASE", default=None)
    DB_DSN = config(
        "DB_DSN",
        cast=make_url,
        default=URL(
            drivername=DB_DRIVER,
            username=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_DATABASE,
        ),
    )
    DB_POOL_MIN_SIZE = config("DB_POOL_MIN_SIZE", cast=int, default=1)
    DB_POOL_MAX_SIZE = config("DB_POOL_MAX_SIZE", cast=int, default=16)
    DB_ECHO = config("DB_ECHO", cast=bool, default=False)
    DB_SSL = config("DB_SSL", default=None)
    DB_USE_CONNECTION_FOR_REQUEST = config(
        "DB_USE_CONNECTION_FOR_REQUEST", cast=bool, default=True
    )
    DB_RETRY_LIMIT = config("DB_RETRY_LIMIT", cast=int, default=1)
    DB_RETRY_INTERVAL = config("DB_RETRY_INTERVAL", cast=int, default=1)

This config file will load from environment variable first, if not found then from a
file named ``.env`` from current path (usually the project root directory), and at last
use the default value defined above. For example, you can either overwrite in CLI
directly like this:

.. code-block:: console

    $ DB_HOST=localhost DB_USER=postgres poetry run uvicorn gino_fastapi_demo.asgi:app --reload

.. image:: ../images/gino-fastapi-env.svg
   :align: right

Or set them in the file ``.env`` (this file must not be committed into Git, remember to
add it to ``.gitignore``):

.. code-block:: bash

    DB_HOST=localhost
    DB_USER=postgres

Now it's time to create a PostgreSQL_ database and set the connection variables
correctly here. This is usually something like ``createdb yourdbname``, but it may vary
across different platforms, so we won't cover this part in this tutorial.

.. tip::

    Alternatively, you could also set ``DB_DSN`` to for example
    ``postgresql://user:password@localhost:5432/dbname`` to override the other individual
    config values like ``DB_HOST`` defined before ``DB_DSN``.

    If defined, ``DB_DSN`` always have the higher priority over the individual ones,
    regardless of where they are defined - even if ``DB_HOST`` is defined in environment
    variable and ``DB_DSN`` is defined in ``.env`` file, ``DB_HOST`` is still ignored.
    Default value doesn't count.

.. image:: ../images/gino-fastapi-models.svg
   :align: right

Then, create a new Python sub-package ``gino_fastapi_demo.models`` to encapsulate
database-related code, and add the code below to
``src/gino_fastapi_demo/models/__init__.py``::

    from gino.ext.starlette import Gino

    from .. import config

    db = Gino(
        dsn=config.DB_DSN,
        pool_min_size=config.DB_POOL_MIN_SIZE,
        pool_max_size=config.DB_POOL_MAX_SIZE,
        echo=config.DB_ECHO,
        ssl=config.DB_SSL,
        use_connection_for_request=config.DB_USE_CONNECTION_FOR_REQUEST,
        retry_limit=config.DB_RETRY_LIMIT,
        retry_interval=config.DB_RETRY_INTERVAL,
    )

At last, modify ``src/gino_fastapi_demo/main.py`` to install the GINO extension:

.. code-block:: diff

     from fastapi import FastAPI
    +
    +from .models import db

     def get_app():
         app = FastAPI(title="GINO FastAPI Demo")
    +    db.init_app(app)
         return app

Saving the file, you should see the Uvicorn server reloads our changes and connects to
the database:

.. code-block:: console

    WARNING:  Detected file change in 'src/gino_fastapi_demo/main.py'. Reloading...
    INFO:     Shutting down
    INFO:     Waiting for application shutdown.
    INFO:     Application shutdown complete.
    INFO:     Finished server process [63562]
    INFO:     Started server process [63563]
    INFO:     Waiting for application startup.
    INFO:     Connecting to the database: postgresql://fantix:***@localhost
    INFO:     Database connection pool created: <asyncpg.pool.Pool max=16 min=1 cur=1 use=0>
    INFO:     Application startup complete.

.. _PostgreSQL: https://www.postgresql.org/


Create Models and API
---------------------

.. image:: ../images/gino-fastapi-models-users.svg
   :align: right

It's time to implement the API now. Let's say we are building a user management service,
through which we could add users, list users and delete users.

First of all, we need a database table ``users`` to store the data, mapped to a GINO
model named ``User``. We shall add the model in ``gino_fastapi_demo.models.users``::

    from . import db

    class User(db.Model):
        __tablename__ = "users"

        id = db.Column(db.BigInteger(), primary_key=True)
        nickname = db.Column(db.Unicode(), default="unnamed")

.. image:: ../images/gino-fastapi-views.svg
   :align: right

The model definition is simple enough to explain itself.

Then we only have to use it properly in the API implementation, for which we'll create a
new Python sub-package ``gino_fastapi_demo.views``, and a new module
``gino_fastapi_demo.views.users`` as follows::

    from fastapi import APIRouter
    from pydantic import BaseModel

    from ..models.users import User

    router = APIRouter()

    @router.get("/users/{uid}")
    async def get_user(uid: int):
        user = await User.get_or_404(uid)
        return user.to_dict()

    class UserModel(BaseModel):
        name: str

    @router.post("/users")
    async def add_user(user: UserModel):
        rv = await User.create(nickname=user.name)
        return rv.to_dict()

    @router.delete("/users/{uid}")
    async def delete_user(uid: int):
        user = await User.get_or_404(uid)
        await user.delete()
        return dict(id=uid)

    def init_app(app):
        app.include_router(router)

The |APIRouter|_ holds our new APIs locally, and ``init_app`` is used to integrate it
into our FastAPI application. Here we want some `inversion of control`_: let's make the
APIs plugable, so that we don't have to import all possible future views manually. We
shall use the `Entry Points`_ feature to load the dependencies. Add this code below to
``gino_fastapi_demo.main``::

    import logging
    from importlib.metadata import entry_points

    logger = logging.getLogger(__name__)

    def load_modules(app=None):
        for ep in entry_points()["gino_fastapi_demo.modules"]:
            logger.info("Loading module: %s", ep.name)
            mod = ep.load()
            if app:
                init_app = getattr(mod, "init_app", None)
                if init_app:
                    init_app(app)

.. hint::

    If you're running Python < 3.8, you'll need this `importlib-metadata backport
    <https://importlib-metadata.readthedocs.io/>`_.

And call it in our application factory:

.. code-block:: diff

     def get_app():
         app = FastAPI(title="GINO FastAPI Demo")
         db.init_app(app)
    +    load_modules(app)
         return app

Finally, define the entry points in ``pyproject.toml`` following the `Poetry document
for plugins <https://python-poetry.org/docs/pyproject/#plugins>`_:

.. code-block:: toml

    [tool.poetry.plugins."gino_fastapi_demo.modules"]
    "users" = "gino_fastapi_demo.views.users"

Run ``poetry install`` again to activate the entry points - you may need to restart the
Uvicorn_ development server manually, as the reloader cannot capture the changes we made
to ``pyproject.toml``.

Now you should be able to see the 3 new APIs on the Swagger UI. But none of them works,
because we still haven't created the database tables.

.. |APIRouter| replace:: ``APIRouter``
.. _APIRouter: https://fastapi.tiangolo.com/tutorial/bigger-applications/#apirouter
.. _inversion of control: https://en.wikipedia.org/wiki/Inversion_of_control
.. _Entry Points: https://docs.python.org/3/library/importlib.metadata.html#entry-points


Integrate with Alembic
----------------------

To get started with Alembic_, run this command in the project root directory:

.. code-block:: console

    $ poetry run alembic init migrations

.. image:: ../images/gino-fastapi-alembic.svg
   :align: right

This will generate a new directory ``migrations`` where Alembic_ will store database
migration revisions. At the same time, an ``alembic.ini`` file is created in the project
root directory. Let's simply add all of them to Git control.

For Alembic_ to use our data models defined with GINO (and of course the database
config), we need to modify ``migrations/env.py`` to connect with the GINO instance:

.. code-block:: diff

     # add your model's MetaData object here
     # for 'autogenerate' support
     # from myapp import mymodel
     # target_metadata = mymodel.Base.metadata
    -target_metadata = None
    +from gino_fastapi_demo.config import DB_DSN
    +from gino_fastapi_demo.main import db, load_modules
    +
    +load_modules()
    +config.set_main_option("sqlalchemy.url", str(DB_DSN))
    +target_metadata = db

Then create our first migration revision with:

.. code-block:: console

    $ poetry run alembic revision --autogenerate -m 'add users table'
    INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
    INFO  [alembic.runtime.migration] Will assume transactional DDL.
    INFO  [alembic.autogenerate.compare] Detected added table 'users'
      Generating migrations/versions/32c0feba61ea_add_users_table.py ...  done

The generated revision file should roughly look like this::

    def upgrade():
        op.create_table(
            "users",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("nickname", sa.Unicode(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    def downgrade():
        op.drop_table("users")

.. hint::

    Whenever there is a change to the database schema in the future, just modify the
    GINO modules and run ``alembic revision --autogenerate`` again to generate new
    revisions to track the change. Remember to review the revision file - you may want
    to adjust it.

Eventually, let's apply this migration, by upgrading to the latest revision:

.. code-block:: console

    $ poetry run alembic upgrade head
    INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
    INFO  [alembic.runtime.migration] Will assume transactional DDL.
    INFO  [alembic.runtime.migration] Running upgrade  -> 32c0feba61ea, add users table

Now all the APIs should be fully operational, try with the Swagger UI.


Write the Tests
---------------

In order not to break our development database with running tests, let's create a
separate database to run tests. Apply this change to ``gino_fastapi_demo.config``:

.. code-block:: diff

     config = Config(".env")

    +TESTING = config("TESTING", cast=bool, default=False)

     DB_DRIVER = config("DB_DRIVER", default="postgresql")
     DB_HOST = config("DB_HOST", default=None)
     DB_PORT = config("DB_PORT", cast=int, default=None)
     DB_USER = config("DB_USER", default=None)
     DB_PASSWORD = config("DB_PASSWORD", cast=Secret, default=None)
     DB_DATABASE = config("DB_DATABASE", default=None)
    +if TESTING:
    +    if DB_DATABASE:
    +        DB_DATABASE += "_test"
    +    else:
    +        DB_DATABASE = "gino_fastapi_demo_test"
     DB_DSN = config(

.. tip::

    You need to run ``createdb`` to actually create the database. If you have set
    ``DB_DATABASE`` in ``.env`` - e.g. ``DB_DATABASE=mydb``, the name of the testing
    database should be ``mydb_test``. Or else, ``gino_fastapi_demo_test``.

Then, let's create our pytest_ fixture in ``tests/conftest.py``::

    import pytest
    from alembic.config import main
    from starlette.config import environ
    from starlette.testclient import TestClient

    environ["TESTING"] = "TRUE"

    @pytest.fixture
    def client():
        from gino_fastapi_demo.main import db, get_app

        main(["--raiseerr", "upgrade", "head"])

        with TestClient(get_app()) as client:
            yield client

        main(["--raiseerr", "downgrade", "base"])

.. image:: ../images/gino-fastapi-tests.svg
   :align: right

This fixture creates all the database tables before running the test, yield a Starlette_
|TestClient|_, and drop all the tables with all the data after the test to maintain a
clean environment for the next test.

Here's a sample test in ``tests/test_users.py``::

    import uuid

    def test_crud(client):
        # create
        nickname = str(uuid.uuid4())
        r = client.post("/users", json=dict(name=nickname))
        r.raise_for_status()

        # retrieve
        url = f"/users/{r.json()['id']}"
        assert client.get(url).json()["nickname"] == nickname

        # delete
        client.delete(url).raise_for_status()
        assert client.get(url).status_code == 404

Then run the test:

.. code-block:: console

    $ poetry run pytest
    =========================== test session starts ===========================
    platform darwin -- Python 3.8.2, pytest-5.4.1, py-1.8.1, pluggy-0.13.1
    rootdir: gino-fastapi-demo
    collected 1 item

    tests/test_users.py .                                               [100%]

    ============================ 1 passed in 1.21s ============================

.. |TestClient| replace:: ``TestClient``
.. _TestClient: https://www.starlette.io/testclient/


Notes for Production
--------------------

Given the popularity of Docker/Kubernetes, we'll build a ``Dockerfile`` for our demo:

.. code-block:: dockerfile

    FROM python:3.8-alpine as base

    FROM base as builder
    RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev make postgresql-dev
    RUN pip install poetry
    COPY . /src/
    WORKDIR /src
    RUN python -m venv /env && . /env/bin/activate && poetry install

    FROM base
    RUN apk add --no-cache postgresql-libs
    COPY --from=builder /env /env
    COPY --from=builder /src /src
    WORKDIR /src
    CMD ["/env/bin/gunicorn", "gino_fastapi_demo.asgi:app", "-b", "0.0.0.0:80", "-k", "uvicorn.workers.UvicornWorker"]

In this ``Dockerfile``, we used 2 phases to separate the building from the production
image to reduce target artifact size. Also, we are using Gunicorn_ with
|UvicornWorker|_ from Uvicorn_ as the worker class for best production reliability.

Let's review what we have in the project.

.. image:: ../images/gino-fastapi-layout.svg
   :align: center

This is the end of the tutorial to build a demo. Below is an incomplete checklist to
go live:

* Set ``DB_RETRY_LIMIT`` to a larger number to allow staring the application server
  before the database is fully ready.
* Implement the same retry logic in ``migrations/env.py`` so that Alembic_ gets the same
  functionality.
* Enable ``DB_SSL`` if needed.
* Write a ``docker-compose.yml`` for other developers to get a quick taste or even use
  it for development.
* Enable CI_, install ``pytest-cov`` and use ``--cov-fail-under`` to guarantee coverage.
* Integrate static code analysis tools and security/CVE checking tools.
* Automate Alembic_ upgrade properly - e.g. after new version is deployed.
* Be aware of the usual security attacks like CSRF_, XSS_, etc.
* Write load tests.

Again, the source code of the demo is available `here
<https://github.com/python-gino/gino-starlette/tree/master/examples/prod_fastapi_demo>`_,
and the source of this tutorial is `here
<https://github.com/python-gino/gino/blob/master/docs/tutorials/fastapi.rst>`_.
Please feel free to submit PRs to fix issues or add your thoughts. Happy hacking!

.. |UvicornWorker| replace:: ``UvicornWorker``
.. _UvicornWorker: https://www.uvicorn.org/deployment/#gunicorn
.. _CI: https://en.wikipedia.org/wiki/Continuous_integration
.. _CSRF: https://en.wikipedia.org/wiki/Cross-site_request_forgery
.. _XSS: https://en.wikipedia.org/wiki/Cross-site_scripting
