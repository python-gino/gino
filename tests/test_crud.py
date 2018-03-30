import random

import pytest

from .models import db, User, UserType, Friendship

pytestmark = pytest.mark.asyncio


async def test_create(engine):
    nickname = 'test_create_{}'.format(random.random())
    u = await User.create(bind=engine, timeout=10,
                          nickname=nickname, age=42, type=UserType.USER)
    assert u.id is not None
    assert u.nickname == nickname
    assert u.type == UserType.USER
    assert u.age == 42

    u2 = await User.get(u.id, bind=engine, timeout=10)
    assert u2.id == u.id
    assert u2.nickname == nickname
    assert u2.type == UserType.USER
    assert u2.age == 42
    assert u2 is not u

    return u


async def test_create_from_instance(engine):
    nickname = 'test_create_from_instance_{}'.format(random.random())
    u = User(nickname='will-be-replaced', type=UserType.USER, age=42)
    u.nickname = nickname
    u.age = 21
    await u.create(bind=engine, timeout=10)
    assert u.id is not None
    assert u.nickname == nickname
    assert u.type == UserType.USER
    assert u.age == 21

    u2 = await User.get(u.id, bind=engine, timeout=10)
    assert u2.id == u.id
    assert u2.nickname == nickname
    assert u2.type == UserType.USER
    assert u2.age == 21
    assert u2 is not u

    return u


async def test_get(engine):
    u1 = await test_create(engine)
    u2 = await User.get(u1.id, bind=engine, timeout=10)
    assert u1.id == u2.id
    assert u1.nickname == u2.nickname
    assert u1 is not u2

    u3 = await engine.first(u1.query)
    assert u1.id == u3.id
    assert u1.nickname == u3.nickname
    assert u1 is not u3

    u4 = await test_create_from_instance(engine)
    u5 = await engine.first(u4.query)
    assert u4.id == u5.id
    assert u4.nickname == u5.nickname
    assert u4 is not u5


async def test_textual_sql(engine):
    u1 = await test_create(engine)
    u2 = await engine.first(db.text(
        'SELECT * FROM gino_users WHERE id = :uid'
    ).bindparams(uid=u1.id).columns(*User).execution_options(model=User))
    assert isinstance(u2, User)
    assert u1.id == u2.id
    assert u1.nickname == u2.nickname
    assert u1.type is u2.type
    assert u1 is not u2

    u2 = await engine.first(db.text(
        'SELECT * FROM gino_users WHERE id = :uid AND type = :utype'
    ).bindparams(
        db.bindparam('utype', type_=db.Enum(UserType))
    ).bindparams(
        uid=u1.id,
        utype=UserType.USER,
    ).columns(*User).execution_options(model=User))
    assert isinstance(u2, User)
    assert u1.id == u2.id
    assert u1.nickname == u2.nickname
    assert u1.type is u2.type
    assert u1 is not u2


async def test_select(engine):
    u = await test_create(engine)
    name = await engine.scalar(User.select('nickname').where(User.id == u.id))
    assert u.nickname == name

    name = await engine.scalar(u.select('nickname'))
    assert u.nickname == name


async def test_get_multiple_primary_key(engine):
    u1 = await test_create(engine)
    u2 = await test_create(engine)
    await Friendship.create(bind=engine, my_id=u1.id, friend_id=u2.id)
    with pytest.raises(ValueError,
                       match='Incorrect number of values as primary key'):
        await Friendship.get((u1.id,), bind=engine)
    with pytest.raises(ValueError,
                       match='Incorrect number of values as primary key'):
        await Friendship.get(u1.id, bind=engine)
    f = await Friendship.get((u1.id, u2.id), bind=engine)
    assert f
    assert f.my_id == u1.id
    assert f.friend_id == u2.id


async def test_connection_as_bind(engine):
    async with engine.acquire() as conn:
        await test_get(conn)


async def test_update(engine, random_name):
    u1 = await test_create(engine)
    await u1.update(nickname=random_name).apply(bind=engine, timeout=10)
    u2 = await User.get(u1.id, bind=engine)
    assert u2.nickname == random_name


async def test_update_missing(engine, random_name):
    from gino.exceptions import NoSuchRowError

    u1 = await test_create(engine)
    rq = u1.update(nickname=random_name)
    await u1.delete(bind=engine)
    with pytest.raises(NoSuchRowError):
        await rq.apply(bind=engine, timeout=10)


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
    await u1.delete(bind=engine, timeout=10)
    u2 = await User.get(u1.id, bind=engine)
    assert not u2


async def test_delete_bind(bind):
    u1 = await test_create(bind)
    await u1.delete(timeout=10)
    u2 = await User.get(u1.id)
    assert not u2


async def test_delete_multiple_primary_key(engine):
    u1 = await test_create(engine)
    u2 = await test_create(engine)
    f = await Friendship.create(bind=engine, my_id=u1.id, friend_id=u2.id)
    await f.delete(bind=engine)
    f2 = await Friendship.get((u1.id, u2.id), bind=engine)
    assert not f2
