import ssl

import aiomysql
import pytest
import sqlalchemy

import gino
from .models import db, DB_ARGS, MYSQL_URL, random_name

ECHO = False


@pytest.fixture(scope="module")
def sa_engine():
    rv = sqlalchemy.create_engine(
        MYSQL_URL.replace("mysql://", "mysql+pymysql://"), echo=ECHO
    )
    db.create_all(rv)
    yield rv
    db.drop_all(rv)
    rv.dispose()


@pytest.fixture
async def engine(sa_engine):
    e = await gino.create_engine(MYSQL_URL, echo=ECHO, minsize=10)
    yield e
    await e.close()
    sa_engine.execute("DELETE FROM gino_user_settings")
    sa_engine.execute("DELETE FROM gino_users")


# noinspection PyUnusedLocal,PyShadowingNames
@pytest.fixture
async def bind(sa_engine):
    async with db.with_bind(MYSQL_URL, echo=ECHO, minsize=10) as e:
        yield e
    sa_engine.execute("DELETE FROM gino_user_settings")
    sa_engine.execute("DELETE FROM gino_users")


# noinspection PyUnusedLocal,PyShadowingNames
@pytest.fixture
async def aiomysql_pool(sa_engine):
    async with aiomysql.create_pool(**DB_ARGS) as rv:
        yield rv
        async with rv.acquire() as conn:
            await conn.query("DELETE FROM gino_user_settings")
            await conn.query("DELETE FROM gino_users")


@pytest.fixture
def ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
