======
|GINO|
======

.. image:: https://img.shields.io/pypi/v/gino?logo=python&logoColor=white
        :alt: PyPI Release Version
        :target: https://pypi.python.org/pypi/gino

.. image:: https://img.shields.io/pypi/dm/gino?logo=pypi&logoColor=white
        :alt: PyPI Monthly Downloads
        :target: https://pypi.python.org/pypi/gino

.. image:: https://img.shields.io/github/workflow/status/python-gino/gino/CI?label=CI&logo=github
        :alt: GitHub Workflow Status for CI
        :target: https://github.com/python-gino/gino/actions?query=workflow%3ACI

.. image:: https://img.shields.io/codacy/grade/b6a59cdf5ca64eab9104928d4f9bbb97?logo=codacy
        :alt: Codacy Code Quality
        :target: https://app.codacy.com/gh/python-gino/gino/dashboard

.. image:: https://img.shields.io/codacy/coverage/b6a59cdf5ca64eab9104928d4f9bbb97?logo=codacy
        :alt: Codacy coverage
        :target: https://app.codacy.com/gh/python-gino/gino/dashboard


GINO - GINO Is Not ORM - is a lightweight asynchronous ORM built on top of
SQLAlchemy_ core for Python asyncio_. GINO 1.0 supports only PostgreSQL_ with asyncpg_.

* Free software: BSD license
* Requires: Python 3.6
* GINO is developed proudly with |PyCharm|.


Home
----

`python-gino.org <https://python-gino.org/>`__


Documentation
-------------

* English_
* Chinese_


Installation
------------

.. code-block:: console

    $ pip install gino


Features
--------

* Robust SQLAlchemy-asyncpg bi-translator with no hard hack
* Asynchronous SQLAlchemy-alike engine and connection
* Asynchronous dialect API
* Asynchronous-friendly CRUD objective models
* Well-considered contextual connection and transaction management
* Reusing native SQLAlchemy core to build queries with grammar sugars
* Support SQLAlchemy ecosystem, e.g. Alembic_ for migration
* `Community support <https://github.com/python-gino/>`_ for Starlette_/FastAPI_, aiohttp_, Sanic_, Tornado_ and Quart_
* Rich PostgreSQL JSONB support


.. _SQLAlchemy: https://www.sqlalchemy.org/
.. _asyncpg: https://github.com/MagicStack/asyncpg
.. _PostgreSQL: https://www.postgresql.org/
.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _Alembic: https://bitbucket.org/zzzeek/alembic
.. _Sanic: https://github.com/channelcat/sanic
.. _Tornado: http://www.tornadoweb.org/
.. _Quart: https://gitlab.com/pgjones/quart/
.. _English: https://python-gino.org/docs/en/
.. _Chinese: https://python-gino.org/docs/zh/
.. _aiohttp: https://github.com/aio-libs/aiohttp
.. _Starlette: https://www.starlette.io/
.. _FastAPI: https://fastapi.tiangolo.com/
.. |PyCharm| image:: ./docs/images/pycharm.svg
        :height: 20px
        :target: https://www.jetbrains.com/?from=GINO

.. |GINO| image:: ./docs/theme/static/logo.svg
        :alt: GINO
        :height: 64px
        :target: https://python-gino.org/
