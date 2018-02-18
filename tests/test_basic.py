import random
from datetime import datetime

import asyncpg
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import ObjectNotExecutableError
from asyncpg.exceptions import InvalidCatalogNameError

from .models import db, User, UserType, Friendship

pytestmark = pytest.mark.asyncio


def _qsize(engine):
    # noinspection PyProtectedMember
    return engine._dialect._pool._queue.qsize()


async def test_basic(engine):
    init_size = _qsize(engine)
    async with engine.acquire() as conn:
        assert isinstance(conn.raw_connection, asyncpg.Connection)
    assert init_size == _qsize(engine)
    assert isinstance(await engine.scalar('select now()'), datetime)
    assert isinstance(await engine.scalar(sa.text('select now()')), datetime)
    assert isinstance((await engine.first('select now()'))[0], datetime)
    assert isinstance((await engine.all('select now()'))[0][0], datetime)
    status, result = await engine.status('select now()')
    assert status == 'SELECT 1'
    assert isinstance(result[0][0], datetime)
    with pytest.raises(ObjectNotExecutableError):
        await engine.all(object())


async def test_create(engine):
    nickname = 'test_create_{}'.format(random.random())
    u = await User.create(bind=engine, nickname=nickname,
                          type=UserType.USER)
    assert u.id is not None
    assert u.nickname == nickname
    assert u.type == UserType.USER
    return u


async def test_get(engine):
    u1 = await test_create(engine)
    u2 = await User.get(u1.id, bind=engine)
    assert u1.id == u2.id
    assert u1.nickname == u2.nickname
    assert u1 is not u2


async def test_get_multiple_primary_key(engine):
    u1 = await test_create(engine)
    u2 = await test_create(engine)
    await Friendship.create(bind=engine, my_id=u1.id, friend_id=u2.id)
    f = await Friendship.get((u1.id, u2.id), bind=engine)
    assert f
    assert f.my_id == u1.id
    assert f.friend_id == u2.id


async def test_connection_as_bind(engine):
    async with engine.acquire() as conn:
        await test_get(conn)


async def test_update(engine, random_name):
    u1 = await test_create(engine)
    await u1.update(nickname=random_name).apply(bind=engine)
    u2 = await User.get(u1.id, bind=engine)
    assert u2.nickname == random_name


async def test_update_multiple_primary_key(engine):
    u1 = await test_create(engine)
    u2 = await test_create(engine)
    u3 = await test_create(engine)
    await Friendship.create(bind=engine, my_id=u1.id, friend_id=u2.id)
    f = await Friendship.get((u1.id, u2.id), bind=engine)
    await f.update(my_id=u2.id, friend_id=u3.id).apply(bind=engine)
    f2 = await Friendship.get((u2.id, u3.id), bind=engine)
    assert f2


async def test_delete(engine):
    u1 = await test_create(engine)
    await u1.delete(bind=engine)
    u2 = await User.get(u1.id, bind=engine)
    assert not u2


async def test_delete_multiple_primary_key(engine):
    u1 = await test_create(engine)
    u2 = await test_create(engine)
    f = await Friendship.create(bind=engine, my_id=u1.id, friend_id=u2.id)
    await f.delete(bind=engine)
    f2 = await Friendship.get((u1.id, u2.id), bind=engine)
    assert not f2


async def test_issue_79():
    import gino
    db = gino.Gino()
    e = await db.create_engine('asyncpg:///non_exist?min_size=0')
    with pytest.raises(InvalidCatalogNameError):
        async with e.acquire():
            pass
    # noinspection PyProtectedMember
    assert len(e._ctx.get([])) == 0


async def test_reuse(engine):
    init_size = _qsize(engine)
    async with engine.acquire(reuse=True) as conn1:
        assert _qsize(engine) == init_size - 1
        async with engine.acquire(reuse=True) as conn2:
            assert _qsize(engine) == init_size - 1
            assert conn1 is conn2
        assert _qsize(engine) == init_size - 1
    assert _qsize(engine) == init_size

    async with engine.acquire(reuse=False) as conn1:
        assert _qsize(engine) == init_size - 1
        async with engine.acquire(reuse=True) as conn2:
            assert _qsize(engine) == init_size - 1
            assert conn1 is conn2
        assert _qsize(engine) == init_size - 1
    assert _qsize(engine) == init_size

    async with engine.acquire(reuse=True) as conn1:
        assert _qsize(engine) == init_size - 1
        async with engine.acquire(reuse=False) as conn2:
            assert _qsize(engine) == init_size - 2
            assert conn1 is not conn2
        assert _qsize(engine) == init_size - 1
    assert _qsize(engine) == init_size

    async with engine.acquire(reuse=False) as conn1:
        assert _qsize(engine) == init_size - 1
        async with engine.acquire(reuse=False) as conn2:
            assert _qsize(engine) == init_size - 2
            assert conn1 is not conn2
        assert _qsize(engine) == init_size - 1
    assert _qsize(engine) == init_size

    async with engine.acquire(reuse=False) as conn1:
        assert _qsize(engine) == init_size - 1
        async with engine.acquire(reuse=True) as conn2:
            assert _qsize(engine) == init_size - 1
            assert conn1 is conn2
            async with engine.acquire(reuse=False) as conn3:
                assert _qsize(engine) == init_size - 2
                assert conn1 is not conn3
                async with engine.acquire(reuse=True) as conn4:
                    assert _qsize(engine) == init_size - 2
                    assert conn3 is conn4
                assert _qsize(engine) == init_size - 2
            assert _qsize(engine) == init_size - 1
        assert _qsize(engine) == init_size - 1
    assert _qsize(engine) == init_size


async def test_compile(engine):
    stmt, params = engine.compile(User.query.where(User.id == 3))
    assert params[0] == 3
