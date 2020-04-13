Welcome to GINO's documentation!
================================

.. image:: https://img.shields.io/pypi/v/gino?logo=python&logoColor=white&color=3E6CDE&style=flat-square
        :alt: PyPI Release Version
        :target: https://pypi.python.org/pypi/gino

.. image:: https://img.shields.io/github/workflow/status/python-gino/gino/test?label=test&logo=github&color=3E6CDE&style=flat-square
        :alt: GitHub Workflow Status for tests
        :target: https://github.com/python-gino/gino/actions?query=workflow%3Atest

.. image:: https://img.shields.io/codacy/coverage/b6a59cdf5ca64eab9104928d4f9bbb97?logo=codacy&color=3E6CDE&style=flat-square
        :alt: Codacy coverage
        :target: https://app.codacy.com/gh/python-gino/gino/dashboard

.. image:: https://img.shields.io/badge/Dependabot-active-brightgreen?logo=dependabot&color=3E6CDE&style=flat-square
        :target: https://app.dependabot.com/accounts/python-gino/projects/129260
        :alt: Dependabot


GINO - GINO Is Not ORM - is a lightweight asynchronous ORM built on top of
SQLAlchemy_ core for Python asyncio_. Now (early 2020) GINO supports only one
dialect asyncpg_.

.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _SQLAlchemy: https://www.sqlalchemy.org/
.. _asyncpg: https://github.com/MagicStack/asyncpg


.. cssclass:: boxed-nav

* .. image:: images/tutorials.svg
   :target: tutorials.html

  :doc:`tutorials`

  Lessons for the newcomer to get started

* .. image:: images/how-to.svg
   :target: how-to.html

  :doc:`how-to`

  Solve specific problems by steps

* .. image:: images/explanation.svg
   :target: explanation.html

  :doc:`explanation`

  Explains the background and context

* .. image:: images/reference.svg
   :target: reference.html

  :doc:`reference`

  Describes the software as it is


Useful Links
------------

.. cssclass:: boxed-nav

* .. image:: images/github.svg
   :target: https://github.com/python-gino/gino

  `Source Code <https://github.com/python-gino/gino>`_

  https://github.com/python-gino/gino

* .. image:: images/community.svg
   :target: https://gitter.im/python-gino/Lobby

  `Community <https://gitter.im/python-gino/Lobby>`_

  https://gitter.im/python-gino/Lobby

* .. image:: images/open-source.svg
   :target: https://github.com/python-gino/gino/blob/master/LICENSE

  `BSD license <https://github.com/python-gino/gino/blob/master/LICENSE>`_

  GINO is free software

* .. image:: images/python.svg
   :target: https://pypi.org/project/gino/

  `Download <https://pypi.org/project/gino/>`_

  Download GINO from PyPI


.. cssclass:: divio

Sections by `Divio <https://www.divio.com/blog/documentation/>`_.

.. toctree::
   :caption: Tutorials
   :maxdepth: 1
   :glob:
   :hidden:

   tutorials
   tutorials/tutorial.rst
   tutorials/*

.. toctree::
   :caption: How-to Guides
   :maxdepth: 1
   :glob:
   :hidden:

   how-to
   how-to/*

.. toctree::
   :caption: Explanation
   :maxdepth: 1
   :glob:
   :hidden:

   explanation
   explanation/*

.. toctree::
   :caption: Reference
   :maxdepth: 1
   :glob:
   :hidden:

   reference
   reference/*
