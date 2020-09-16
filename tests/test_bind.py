import random

import pytest
from gino.exceptions import UninitializedError
from sqlalchemy.engine.url import make_url

from .models import db, DB_ARGS, PG_URL, User

pytestmark = pytest.mark.asyncio


# noinspection PyUnusedLocal
async def test_create(bind):
    nickname = "test_create_{}".format(random.random())
    u = await User.create(nickname=nickname)
    assert u.id is not None
    assert u.nickname == nickname
    return u


async def test_get(bind):
    u1 = await test_create(bind)
    u2 = await User.get(u1.id)
    assert u1.id == u2.id
    assert u1.nickname == u2.nickname
    assert u1 is not u2


# noinspection PyUnusedLocal
async def test_unbind(asyncpg_pool):
    await db.set_bind(PG_URL)
    await test_create(None)
    await db.pop_bind().close()
    db.bind = None
    with pytest.raises(UninitializedError):
        await test_create(None)
    # test proper exception when engine is not initialized
    with pytest.raises(UninitializedError):
        db.bind.first = lambda x: 1


async def test_db_api(bind, random_name):
    assert (
        await db.scalar(User.insert().values(name=random_name).returning(User.nickname))
        == random_name
    )
    assert (
        await db.first(User.query.where(User.nickname == random_name))
    ).nickname == random_name
    assert len(await db.all(User.query.where(User.nickname == random_name))) == 1
    assert (await db.status(User.delete.where(User.nickname == random_name)))[
        0
    ] == "DELETE 1"
    stmt, params = db.compile(User.query.where(User.id == 3))
    assert params[0] == 3


@pytest.mark.parametrize(
    "dsn, driver_name",
    (
        (
            "postgresql://{user}:{password}@{host}:{port}/{database}".format(**DB_ARGS),
            "postgresql",
        ),
        (
            "postgres://{user}:{password}@{host}:{port}/{database}".format(**DB_ARGS),
            "postgres",
        ),
        (
            "postgres://{user}:{password}@/{database}?host={host}&port={port}".format(
                **DB_ARGS
            ),
            "postgres",
        ),
    ),
)
async def test_bind_url(dsn, driver_name):
    url = make_url(dsn)
    assert url.drivername == driver_name
    await db.set_bind(dsn)
    assert url.drivername == driver_name
    await db.pop_bind().close()
