Welcome to GINO's documentation!
================================

.. image:: https://img.shields.io/pypi/v/gino?logo=python&logoColor=white
        :alt: PyPI Release Version
        :target: https://pypi.python.org/pypi/gino

.. image:: https://img.shields.io/github/workflow/status/python-gino/gino/test?logo=github
        :alt: GitHub Workflow Status
        :target: https://github.com/python-gino/gino/actions?query=workflow%3Apytest

GINO - GINO Is Not ORM - is a lightweight asynchronous ORM built on top of
SQLAlchemy_ core for Python asyncio_. Now (early 2020) GINO supports only one
dialect asyncpg_.

.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _SQLAlchemy: https://www.sqlalchemy.org/
.. _asyncpg: https://github.com/MagicStack/asyncpg


.. cssclass:: boxed-nav

* .. image:: images/tutorials.png
   :target: tutorials/tutorial.html

  :doc:`tutorials/tutorial`

  Lessons for the newcomer to get started

* .. image:: images/how-to.png
   :target: how-to.html

  :doc:`how-to`

  Solve specific problems by steps

* .. image:: images/explanation.png
   :target: explanation.html

  :doc:`explanation`

  Explains the background and context

* .. image:: images/reference.png
   :target: reference.html

  :doc:`reference`

  Describes the software as it is

* .. image:: images/github.png
   :target: https://github.com/python-gino/gino

  `Source Code <https://github.com/python-gino/gino>`_

  https://github.com/python-gino/gino

* .. image:: images/community.png
   :target: https://gitter.im/python-gino/Lobby

  `Community <https://gitter.im/python-gino/Lobby>`_

  https://gitter.im/python-gino/Lobby

* .. image:: images/open-source.png
   :target: https://github.com/python-gino/gino/blob/master/LICENSE

  `BSD license <https://github.com/python-gino/gino/blob/master/LICENSE>`_

  GINO is free software

* .. image:: images/python.png
   :target: https://www.python.org/

  `Python 3.5 <https://www.python.org/>`_

  Requires Python 3.5 or above


.. cssclass:: icons8

Icons by `icons8 <https://icons8.com/>`_. Sections by `Divio <https://www.divio.com/blog/documentation/>`_.

.. toctree::
   :caption: Tutorials
   :maxdepth: 1
   :glob:
   :hidden:

   tutorials
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
