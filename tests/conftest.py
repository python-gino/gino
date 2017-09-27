import random
import string

import asyncpg
import pytest
import sqlalchemy

import gino
from .models import db, DB_ARGS


@pytest.fixture(scope='module')
def engine():
    rv = sqlalchemy.create_engine(
        'postgresql://{user}:{password}@{host}:{port}/{database}'.format(
            **DB_ARGS))
    db.create_all(rv)
    yield rv
    db.drop_all(rv)
    rv.dispose()


# noinspection PyUnusedLocal,PyShadowingNames
@pytest.fixture
async def pool(engine):
    async with db.create_pool(**DB_ARGS) as rv:
        yield rv
        await rv.execute('DELETE FROM gino_users')


# noinspection PyUnusedLocal,PyShadowingNames
@pytest.fixture
async def asyncpg_pool(engine):
    async with asyncpg.create_pool(**DB_ARGS) as rv:
        yield rv
        await rv.execute('DELETE FROM gino_users')


@pytest.fixture
def random_name(length=8) -> str:
    return ''.join(random.choice(string.ascii_letters) for _ in range(length))


@pytest.fixture
def task_local(event_loop):
    gino.enable_task_local(event_loop)
    yield
    gino.disable_task_local(event_loop)
