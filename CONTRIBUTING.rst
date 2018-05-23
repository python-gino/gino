.. highlight:: console

============
Contributing
============

Contributions are welcome, and they are greatly appreciated! Every
little bit helps, and credit will always be given.

You can contribute in many ways:

Types of Contributions
----------------------

Report Bugs
~~~~~~~~~~~

Report bugs at https://github.com/fantix/gino/issues.

If you are reporting a bug, please include:

* Your operating system name and version.
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.

Fix Bugs
~~~~~~~~

Look through the GitHub issues for bugs. Anything tagged with "bug"
and "help wanted" is open to whoever wants to implement it.

Implement Features
~~~~~~~~~~~~~~~~~~

Look through the GitHub issues for features. Anything tagged with "enhancement"
and "help wanted" is open to whoever wants to implement it.

Write Documentation
~~~~~~~~~~~~~~~~~~~

GINO could always use more documentation, whether as part of the
official GINO docs, in docstrings, or even on the web in blog posts,
articles, and such.

Submit Feedback
~~~~~~~~~~~~~~~

The best way to send feedback is to file an issue at https://github.com/fantix/gino/issues.

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.
* Remember that this is a volunteer-driven project, and that contributions
  are welcome :)

Get Started!
------------

Ready to contribute? Here's how to set up `gino` for local development.

1. Fork the `gino` repo on GitHub.
2. Clone your fork locally::

    $ git clone git@github.com:your_name_here/gino.git

3. Create a branch for local development::

    $ cd gino/
    $ git checkout -b name-of-your-bugfix-or-feature

Now you can make your changes locally.

4. Create virtual environment. Example for virtualenvwrapper::

    $ mkvirtualenv gino

5. Activate the environment and install requirements::

    $ pip install -r requirements_dev.txt

6. When you're done making changes, check that your changes pass syntax checks::

    $ flake8 gino tests

7. And tests (including other Python versions with tox).
For tests you you will need running database server (see "Tips" section below for configuration details)::

    $ pytest tests
    $ tox

8. For docs run::

    $ make docs

It will build and open up docs in your browser.

9. Commit your changes and push your branch to GitHub::

    $ git add .
    $ git commit -m "Your detailed description of your changes."
    $ git push origin name-of-your-bugfix-or-feature

10. Submit a pull request through the GitHub website.

Pull Request Guidelines
-----------------------

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests.
2. If the pull request adds functionality, the docs should be updated. Put
   your new functionality into a function with a docstring, and add the
   feature to the list in README.rst.
3. The pull request should work for Python 3.6. Check
   https://travis-ci.org/fantix/gino/pull_requests
   and make sure that the tests pass for all supported Python versions.

Tips
----

To run a subset of tests::

$ py.test -svx tests.test_gino

By default the tests run against a default installed postgres database. If you
wish to run against a separate database for the tests you can do this by first
creating a new database and user using 'psql' or similar::

    CREATE ROLE gino WITH LOGIN ENCRYPTED PASSWORD 'gino';
    CREATE DATABASE gino WITH OWNER = gino;

Then run the tests like so::

    $ export DB_USER=gino DB_PASS=gino DB_NAME=gino
    $ py.test

Here is an example for db server in docker.
Terminal 1 (server)::

    $ docker run --rm -it -p 5433:5432 postgres:10

Terminal 2 (client)::

    $ psql -h localhost -p 5433 -U postgres

Now run create role/database commands described above.

Terminal 3 (python)::

    $ export DB_USER=gino DB_PASS=gino DB_NAME=gino DB_PORT=5433
    $ pytest tests/test_aiohttp.py
