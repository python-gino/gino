import ssl

import asyncpg
import pytest
import sqlalchemy
from async_generator import yield_, async_generator

import gino
from .models import db, DB_ARGS, PG_URL, random_name

ECHO = False


@pytest.fixture(scope='module')
def sa_engine():
    rv = sqlalchemy.create_engine(PG_URL, echo=ECHO)
    db.create_all(rv)
    yield rv
    db.drop_all(rv)
    rv.dispose()


@pytest.fixture
@async_generator
async def engine(sa_engine):
    e = await gino.create_engine(PG_URL, echo=ECHO)
    await yield_(e)
    await e.close()
    sa_engine.execute('DELETE FROM gino_user_settings')
    sa_engine.execute('DELETE FROM gino_users')


# noinspection PyUnusedLocal,PyShadowingNames
@pytest.fixture
@async_generator
async def bind(sa_engine):
    async with db.with_bind(PG_URL, echo=ECHO) as e:
        await yield_(e)
    sa_engine.execute('DELETE FROM gino_user_settings')
    sa_engine.execute('DELETE FROM gino_users')


# noinspection PyUnusedLocal,PyShadowingNames
@pytest.fixture
@async_generator
async def asyncpg_pool(sa_engine):
    async with asyncpg.create_pool(**DB_ARGS) as rv:
        await yield_(rv)
        await rv.execute('DELETE FROM gino_user_settings')
        await rv.execute('DELETE FROM gino_users')


@pytest.fixture
def ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
