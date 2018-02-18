import random

import pytest
from .models import db, ASYNCPG_URL, User

pytestmark = pytest.mark.asyncio


# noinspection PyUnusedLocal
async def test_create(bind):
    nickname = 'test_create_{}'.format(random.random())
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
    await db.create_engine(ASYNCPG_URL)
    await test_create(None)
    await db.dispose_engine()
    with pytest.raises(AttributeError):
        await test_create(None)
