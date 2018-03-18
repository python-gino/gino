=======
Welcome
=======

.. image:: https://img.shields.io/pypi/v/gino.svg
    :target: https://pypi.python.org/pypi/gino

.. image:: https://img.shields.io/travis/fantix/gino/master.svg
    :target: https://travis-ci.org/fantix/gino

.. image:: https://img.shields.io/coveralls/github/fantix/gino/master.svg
    :target: https://coveralls.io/github/fantix/gino?branch=master

.. image:: https://img.shields.io/readthedocs/python-gino/stable.svg
    :target: https://python-gino.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://pyup.io/repos/github/fantix/gino/shield.svg
    :target: https://pyup.io/repos/github/fantix/gino/
        :alt: Updates

.. image:: https://img.shields.io/gitter/room/python-gino/Lobby.svg
    :target: https://gitter.im/python-gino/Lobby
        :alt: Gitter chat


GINO - GINO Is Not ORM - is a lightweight asynchronous ORM built on top of
SQLAlchemy_ core for Python asyncio_. Now (early 2018) GINO supports only one
dialect asyncpg_.

* Free software: BSD license
* Requires: Python 3.6
* Source code: https://github.com/fantix/gino
* Community: https://gitter.im/python-gino/Lobby

If you were using GINO 0.5.x, please read `Migrating to GINO 0.6
<history.html#migrating-to-gino-0-6>`_ first.

This documentation is still under development. Please excuse the WIP pages.

.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _SQLAlchemy: https://www.sqlalchemy.org/
.. _asyncpg: https://github.com/MagicStack/asyncpg

============
Translations
============

* English_
* Chinese_

.. _English: https://python-gino.readthedocs.io/
.. _Chinese: https://python-gino.readthedocs.io/zh/latest/

========
Contents
========

.. toctree::
   :maxdepth: 2

   tutorial
   schema
   engine
   transaction
   crud
   sanic
   tornado
   adv_topics
   faq
   api
   contributing
   authors
   history

====================
Module Documentation
====================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
