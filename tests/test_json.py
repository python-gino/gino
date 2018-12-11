import pytest
from datetime import datetime, timedelta

from gino.exceptions import UnknownJSONPropertyError

from .models import db, User, UserType

pytestmark = pytest.mark.asyncio


async def test_in_memory():
    u = User()
    assert u.age == 18
    u.age += 10
    assert u.age == 28
    assert u.balance == 0
    assert isinstance(u.balance, float)


# noinspection PyUnusedLocal
async def test_crud(bind):
    from gino.json_support import DATETIME_FORMAT
    now = datetime.utcnow()
    now_str = now.strftime(DATETIME_FORMAT)
    u = await User.create(nickname='fantix', birthday=now)
    u.age += 1
    assert await u.query.gino.model(None).first() == (
        1, 'fantix', {'age': 18, 'birthday': now_str}, UserType.USER, None)

    u = await User.get(u.id)
    assert u.nickname == 'fantix'
    assert u.birthday == now
    assert u.age == 18
    assert u.balance == 0
    assert isinstance(u.balance, float)
    assert await db.select([User.birthday]).where(
        User.id == u.id).gino.scalar() == now

    # In-memory update, not applying
    u.update(birthday=now - timedelta(days=3650))

    # Update two JSON fields, one using expression
    await u.update(age=User.age - 2, balance=100.85).apply()

    assert u.birthday == now - timedelta(days=3650)
    assert u.age == 16
    assert u.balance == 100
    assert isinstance(u.balance, float)
    assert await u.query.gino.model(None).first() == (
        1, 'fantix', dict(age=16, balance=100, birthday=now_str),
        UserType.USER, None)
    assert await db.select([User.realname]).where(
        User.id == u.id).gino.scalar() is None

    # Reload and test updating both JSON and regular property
    u = await User.get(u.id)
    await u.update(age=User.age - 2, balance=200.15, realname='daisy',
                   nickname='daisy.nick').apply()
    assert await u.query.gino.model(None).first() == (
        1, 'daisy.nick',
        dict(age=14, balance=200, realname='daisy', birthday=now_str),
        UserType.USER, None)
    assert u.to_dict() == dict(
        age=14,
        balance=200.0,
        birthday=now,
        id=1,
        nickname='daisy.nick',
        realname='daisy',
        type=UserType.USER,
        team_id=None,
    )

    # Deleting property doesn't affect database
    assert u.balance == 200
    u.balance = 300
    assert u.balance == 300
    del u.balance
    assert u.balance == 0
    assert await db.select([User.balance]).where(
        User.id == u.id).gino.scalar() == 200
    await u.update(age=22).apply()
    assert u.balance == 0
    assert await db.select([User.balance]).where(
        User.id == u.id).gino.scalar() == 200
    await u.update(balance=None).apply()
    assert u.balance == 0
    assert await db.select([User.balance]).where(
        User.id == u.id).gino.scalar() is None


# noinspection PyUnusedLocal
async def test_non_jsonb(bind):
    from gino.dialects.asyncpg import JSON

    class News(db.Model):
        __tablename__ = 'news'

        id = db.Column(db.Integer(), primary_key=True)
        profile = db.Column(JSON(), nullable=False, server_default='{}')
        visits = db.IntegerProperty(default=0)

    await News.gino.create()
    try:
        news = await News.create()
        assert news.visits == 0
        with pytest.raises(TypeError, match='JSON is not supported'):
            await news.update(visits=News.visits + 10).apply()
        assert news.visits == 0
        with pytest.raises(TypeError, match='JSON is not supported'):
            await news.update(visits=10).apply()
        assert news.visits == 10
        assert await news.select('visits').gino.scalar() == 0
        await news.update(profile=dict(visits=20)).apply()
        assert news.visits == 10
        assert await news.select('visits').gino.scalar() == 20
    finally:
        await News.gino.drop()


# noinspection PyUnusedLocal
async def test_reload(bind):
    u = await User.create()
    await u.update(realname=db.cast('888', db.Unicode)).apply()
    assert u.realname == '888'
    await u.update(profile=None).apply()
    assert u.realname == '888'
    User.__dict__['realname'].reload(u)
    assert u.realname is None


# noinspection PyUnusedLocal
async def test_properties(bind):
    from gino.dialects.asyncpg import JSONB

    class PropsTest(db.Model):
        __tablename__ = 'props_test'
        profile = db.Column(JSONB(), nullable=False, server_default='{}')

        raw = db.JSONProperty()
        bool = db.BooleanProperty()
        obj = db.ObjectProperty()
        arr = db.ArrayProperty()

    await PropsTest.gino.create()
    try:
        t = await PropsTest.create(
            raw=dict(a=[1, 2]),
            bool=True,
            obj=dict(x=1, y=2),
            arr=[3, 4, 5, 6],
        )
        assert t.obj['x'] == 1
        assert t.arr[-1] == 6
        assert await db.select([
            PropsTest.profile,
            PropsTest.raw,
            PropsTest.bool,
        ]).gino.first() == (
                   {'arr': [3, 4, 5, 6], 'obj': {'x': 1, 'y': 2},
                    'raw': {'a': [1, 2]}, 'bool': True},
                   dict(a=[1, 2]),
                   True)
        t.obj = dict(x=10, y=20)
        assert t.obj['x'] == 10
        t.arr = [4, 5, 6, 7]
        assert t.arr[-1] == 7
    finally:
        await PropsTest.gino.drop()


# noinspection PyUnusedLocal
async def test_unknown_properties(bind):
    from gino.dialects.asyncpg import JSONB

    class PropsTest1(db.Model):
        __tablename__ = 'props_test1'
        profile = db.Column(JSONB(), nullable=False, server_default='{}')
        bool = db.BooleanProperty()

    await PropsTest1.gino.create()
    try:
        # bool1 is not defined in the model
        t = await PropsTest1.create(profile=dict(bool1=True))
        with pytest.raises(UnknownJSONPropertyError, match=r'bool1.*profile'):
            t.to_dict()
    finally:
        await PropsTest1.gino.drop()


async def test_no_profile():
    with pytest.raises(AttributeError, match=r'JSON\[B\] column'):
        # noinspection PyUnusedLocal
        class Test(db.Model):
            __tablename__ = 'tests_no_profile'

            age = db.IntegerProperty(default=18)


async def test_t291_t402(bind):
    from gino.dialects.asyncpg import JSON, JSONB

    class CustomJSONB(db.TypeDecorator):
        impl = JSONB

        def process_result_value(self, *_):
            return 123

    class PropsTest(db.Model):
        __tablename__ = 'props_test_291'
        profile = db.Column(JSONB(), nullable=False, server_default='{}')
        profile1 = db.Column(JSON(), nullable=False, server_default='{}')
        profile2 = db.Column(CustomJSONB(),
                             nullable=False, server_default='{}')

        bool = db.BooleanProperty()
        bool1 = db.BooleanProperty(prop_name='profile1')

    await PropsTest.gino.create()
    try:
        t = await PropsTest.create(
            bool=True,
            bool1=True,
        )
        profile = await bind.scalar('SELECT profile FROM props_test_291')
        assert isinstance(profile, dict)
        profile1 = await bind.scalar('SELECT profile1 FROM props_test_291')
        assert isinstance(profile1, dict)
        profile2 = await bind.scalar('SELECT profile2 FROM props_test_291')
        assert isinstance(profile2, dict)
        custom_profile2 = await bind.scalar(PropsTest.select('profile2'))
        assert isinstance(custom_profile2, int)
        assert custom_profile2 == 123
    finally:
        await PropsTest.gino.drop()
