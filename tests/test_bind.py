import random

import pytest
from .models import db, DB_ARGS, User

pytestmark = pytest.mark.asyncio


# noinspection PyUnusedLocal
async def test_create(pool):
    nickname = 'test_create_{}'.format(random.random())
    u = await User.create(nickname=nickname)
    assert u.id is not None
    assert u.nickname == nickname
    return u


async def test_get(pool):
    u1 = await test_create(pool)
    u2 = await User.get(u1.id)
    assert u1.id == u2.id
    assert u1.nickname == u2.nickname
    assert u1 is not u2


async def test_unbind():
    try:
        async with db.create_pool(**DB_ARGS):
            await test_create(None)
        with pytest.raises(AttributeError):
            await test_create(None)
    finally:
        async with db.create_pool(**DB_ARGS) as pool:
            await pool.execute('DELETE FROM gino_users')
