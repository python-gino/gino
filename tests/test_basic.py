import random

import pytest
from .models import User, Friendship

pytestmark = pytest.mark.asyncio


async def test_create(asyncpg_pool):
    nickname = 'test_create_{}'.format(random.random())
    u = await User.create(bind=asyncpg_pool, nickname=nickname)
    assert u.id is not None
    assert u.nickname == nickname
    return u


async def test_get(asyncpg_pool):
    u1 = await test_create(asyncpg_pool)
    u2 = await User.get(u1.id, bind=asyncpg_pool)
    assert u1.id == u2.id
    assert u1.nickname == u2.nickname
    assert u1 is not u2


async def test_get_multiple_primary_key(asyncpg_pool):
    u1 = await test_create(asyncpg_pool)
    u2 = await test_create(asyncpg_pool)
    await Friendship.create(bind=asyncpg_pool, my_id=u1.id, friend_id=u2.id)
    f = await Friendship.get((u1.id, u2.id), bind=asyncpg_pool)
    assert f
    assert f.my_id == u1.id
    assert f.friend_id == u2.id


async def test_connection_as_bind(asyncpg_pool):
    async with asyncpg_pool.acquire() as conn:
        await test_get(conn)
