=====================
Engine and Connection
=====================

**THIS IS A WIP**

Different from :func:`sqlalchemy.create_engine`, GINO's version sets the
default strategy to :class:`~gino.strategies.GinoStrategy` - an asynchronous
SQLAlchemy engine strategy that generates asynchronous engines and connections.
Also :class:`~gino.strategies.GinoStrategy` replaces the default dialect of
``postgresql://`` from psycopg2 to asyncpg.
