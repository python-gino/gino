import pytest

from gino import MultipleResultsFound, NoResultFound
from .models import db, User

pytestmark = pytest.mark.asyncio


# noinspection PyUnusedLocal
async def test_status(bind):
    statement, params = db.compile(User.insert(), [dict(name="1"), dict(name="2")])
    assert statement == ("INSERT INTO gino_users (name, type) " "VALUES ($1, $2)")
    assert params == (("1", "USER"), ("2", "USER"))
    result = await User.insert().gino.status(dict(name="1"), dict(name="2"))
    assert result is None
    assert len(await User.query.gino.all()) == 2


# noinspection PyUnusedLocal
async def test_all(bind):
    result = (
        await User.insert()
        .returning(User.nickname)
        .gino.all(dict(name="1"), dict(name="2"))
    )
    assert result is None
    rows = await User.query.gino.all()
    assert len(rows) == 2
    assert set(u.nickname for u in rows) == {"1", "2"}

    result = await User.insert().gino.all(dict(name="3"), dict(name="4"))
    assert result is None
    rows = await User.query.gino.all()
    assert len(rows) == 4
    assert set(u.nickname for u in rows) == {"1", "2", "3", "4"}


# noinspection PyUnusedLocal
async def test_first(bind):
    result = (
        await User.insert()
        .returning(User.nickname)
        .gino.first(dict(name="1"), dict(name="2"))
    )
    assert result is None
    rows = await User.query.gino.all()
    assert len(await User.query.gino.all()) == 2
    assert set(u.nickname for u in rows) == {"1", "2"}

    result = await User.insert().gino.first(dict(name="3"), dict(name="4"))
    assert result is None
    rows = await User.query.gino.all()
    assert len(rows) == 4
    assert set(u.nickname for u in rows) == {"1", "2", "3", "4"}


# noinspection PyUnusedLocal
async def test_one_or_none(bind):
    row = await User.query.gino.one_or_none()
    assert row is None

    await User.create(nickname="0")
    row = await User.query.gino.one_or_none()
    assert row.nickname == "0"

    result = (
        await User.insert()
        .returning(User.nickname)
        .gino.one_or_none(dict(name="1"), dict(name="2"))
    )
    assert result is None
    rows = await User.query.gino.all()
    assert len(await User.query.gino.all()) == 3
    assert set(u.nickname for u in rows) == {"0", "1", "2"}

    with pytest.raises(MultipleResultsFound):
        row = await User.query.gino.one_or_none()


# noinspection PyUnusedLocal
async def test_one(bind):
    with pytest.raises(NoResultFound):
        row = await User.query.gino.one()

    await User.create(nickname="0")
    row = await User.query.gino.one()
    assert row.nickname == "0"

    with pytest.raises(NoResultFound):
        await User.insert().returning(User.nickname).gino.one(
            dict(name="1"), dict(name="2")
        )
    rows = await User.query.gino.all()
    assert len(await User.query.gino.all()) == 3
    assert set(u.nickname for u in rows) == {"0", "1", "2"}

    with pytest.raises(MultipleResultsFound):
        row = await User.query.gino.one()


# noinspection PyUnusedLocal
async def test_scalar(bind):
    result = (
        await User.insert()
        .returning(User.nickname)
        .gino.scalar(dict(name="1"), dict(name="2"))
    )
    assert result is None
    rows = await User.query.gino.all()
    assert len(await User.query.gino.all()) == 2
    assert set(u.nickname for u in rows) == {"1", "2"}

    result = await User.insert().gino.scalar(dict(name="3"), dict(name="4"))
    assert result is None
    rows = await User.query.gino.all()
    assert len(rows) == 4
    assert set(u.nickname for u in rows) == {"1", "2", "3", "4"}
