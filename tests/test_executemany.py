import pytest

from .models import db, User

pytestmark = pytest.mark.asyncio


# noinspection PyUnusedLocal
async def test_status(bind):
    statement, params = db.compile(User.insert(),
                                   [dict(name='1'), dict(name='2')])
    assert statement == ('INSERT INTO gino_users (name, type) '
                         'VALUES ($1, $2)')
    assert params == (('1', 'USER'), ('2', 'USER'))
    result = await User.insert().gino.status(dict(name='1'), dict(name='2'))
    assert result is None
    assert len(await User.query.gino.all()) == 2


# noinspection PyUnusedLocal
async def test_all(bind):
    result = await User.insert().returning(User.nickname).gino.all(
        dict(name='1'), dict(name='2'))
    assert result is None
    rows = await User.query.gino.all()
    assert len(rows) == 2
    assert set(u.nickname for u in rows) == {'1', '2'}

    result = await User.insert().gino.all(
        dict(name='3'), dict(name='4'))
    assert result is None
    rows = await User.query.gino.all()
    assert len(rows) == 4
    assert set(u.nickname for u in rows) == {'1', '2', '3', '4'}


# noinspection PyUnusedLocal
async def test_first(bind):
    result = await User.insert().returning(User.nickname).gino.first(
        dict(name='1'), dict(name='2'))
    assert result is None
    rows = await User.query.gino.all()
    assert len(await User.query.gino.all()) == 2
    assert set(u.nickname for u in rows) == {'1', '2'}

    result = await User.insert().gino.first(
        dict(name='3'), dict(name='4'))
    assert result is None
    rows = await User.query.gino.all()
    assert len(rows) == 4
    assert set(u.nickname for u in rows) == {'1', '2', '3', '4'}


# noinspection PyUnusedLocal
async def test_scalar(bind):
    result = await User.insert().returning(User.nickname).gino.scalar(
        dict(name='1'), dict(name='2'))
    assert result is None
    rows = await User.query.gino.all()
    assert len(await User.query.gino.all()) == 2
    assert set(u.nickname for u in rows) == {'1', '2'}

    result = await User.insert().gino.scalar(
        dict(name='3'), dict(name='4'))
    assert result is None
    rows = await User.query.gino.all()
    assert len(rows) == 4
    assert set(u.nickname for u in rows) == {'1', '2', '3', '4'}
