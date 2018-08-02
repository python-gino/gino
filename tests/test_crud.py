import random

import pytest

from .models import db, User, UserType, Friendship, Relation, PG_URL

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


async def test_multiple_primary_key_order():
    import gino

    db1 = await gino.Gino(PG_URL)

    class NameCard(db1.Model):
        __tablename__ = 'name_cards'

        first_name = db1.Column(db1.Unicode(), primary_key=True)
        last_name = db1.Column(db1.Unicode(), primary_key=True)

    await db1.gino.create_all()

    try:
        await NameCard.create(first_name='first', last_name='last')
        nc = await NameCard.get(('first', 'last'))
        assert nc.first_name == 'first'
        assert nc.last_name == 'last'
        with pytest.raises(ValueError, match='expected 2, got 3'):
            await NameCard.get(dict(a=1, first_name='first', last_name='last'))
        with pytest.raises(KeyError, match='first_name'):
            await NameCard.get(dict(first='first', last_name='last'))
        nc = await NameCard.get(dict(first_name='first', last_name='last'))
        assert nc.first_name == 'first'
        assert nc.last_name == 'last'
        nc = await NameCard.get({0: 'first', 1: 'last'})
        assert nc.first_name == 'first'
        assert nc.last_name == 'last'
    finally:
        await db1.gino.drop_all()
        await db1.pop_bind().close()

    db2 = await gino.Gino(PG_URL)

    class NameCard(db2.Model):
        __tablename__ = 'name_cards'

        last_name = db2.Column(db2.Unicode(), primary_key=True)
        first_name = db2.Column(db2.Unicode(), primary_key=True)

    await db2.gino.create_all()

    try:
        await NameCard.create(first_name='first', last_name='last')
        nc = await NameCard.get(('last', 'first'))
        assert nc.first_name == 'first'
        assert nc.last_name == 'last'
        nc = await NameCard.get(dict(first_name='first', last_name='last'))
        assert nc.first_name == 'first'
        assert nc.last_name == 'last'
        nc = await NameCard.get({1: 'first', 'last_name': 'last'})
        assert nc.first_name == 'first'
        assert nc.last_name == 'last'
    finally:
        await db2.gino.drop_all()
        await db2.pop_bind().close()


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


async def test_string_primary_key(engine):
    relations = ['Colleagues', 'Friends', 'Lovers']
    for r in relations:
        await Relation.create(bind=engine, timeout=10, name=r)
    r1 = await Relation.get(relations[0], bind=engine, timeout=10)
    assert r1.name == relations[0]


async def test_lookup_287(bind):
    from gino.exceptions import NoSuchRowError

    class Game(db.Model):
        __tablename__ = 'games'
        game_id = db.Column(db.String(32), unique=True)
        channel_id = db.Column(db.String(1), default='A')

    await Game.gino.create()
    try:
        game_1 = await Game.create(game_id='1', channel_id='X')
        game_2 = await Game.create(game_id='2', channel_id='Y')

        # ordinary update should be fine
        uq = game_1.update(game_id='3')

        with pytest.raises(TypeError,
                           match='Model Game has no table, primary key'):
            # but applying the updates to DB should fail
            await uq.apply()

        with pytest.raises(LookupError,
                           match='Instance-level CRUD operations not allowed'):
            await game_2.delete()
        with pytest.raises(LookupError,
                           match='Instance-level CRUD operations not allowed'):
            await game_2.query.gino.all()
        with pytest.raises(LookupError,
                           match='Instance-level CRUD operations not allowed'):
            await game_2.select('game_id')

        # previous ordinary update still in effect
        assert game_1.game_id == '3'

        assert await Game.select('game_id').gino.all() == [('1',), ('2',)]

        Game.lookup = lambda self: Game.game_id == self.game_id
        with pytest.raises(NoSuchRowError):
            await game_1.update(channel_id='Z').apply()
        await game_2.update(channel_id='Z').apply()
        assert await Game.select('channel_id').gino.all() == [('X',), ('Z',)]
    finally:
        await Game.gino.drop()
