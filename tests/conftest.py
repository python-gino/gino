import random
import string

import asyncpg
import pytest
import sqlalchemy

import gino
from .models import db, DB_ARGS, ASYNCPG_URL

ECHO = False


@pytest.fixture(scope='module')
def sa_engine():
    rv = sqlalchemy.create_engine(
        'postgresql://{user}:{password}@{host}:{port}/{database}'.format(
            **DB_ARGS), echo=ECHO)
    db.create_all(rv)
    yield rv
    db.drop_all(rv)
    rv.dispose()


@pytest.fixture
async def engine(sa_engine):
    e = await gino.create_engine(ASYNCPG_URL, echo=ECHO)
    yield e
    await e.close()
    sa_engine.execute('DELETE FROM gino_users')


# noinspection PyUnusedLocal,PyShadowingNames
@pytest.fixture
async def bind(sa_engine):
    rv = await db.create_engine(ASYNCPG_URL, echo=ECHO)
    yield rv
    await db.dispose_engine()
    sa_engine.execute('DELETE FROM gino_users')


# noinspection PyUnusedLocal,PyShadowingNames
@pytest.fixture
async def asyncpg_pool(sa_engine):
    async with asyncpg.create_pool(**DB_ARGS) as rv:
        yield rv
        await rv.execute('DELETE FROM gino_users')


@pytest.fixture
def random_name(length=8) -> str:
    return ''.join(random.choice(string.ascii_letters) for _ in range(length))
