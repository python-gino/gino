import pytest

from .models import db, User

pytestmark = pytest.mark.asyncio


# noinspection PyUnusedLocal
async def test_status(bind):
    statement, params = db.compile(User.insert(),
                                   [dict(nickname='1'), dict(nickname='2')])
    assert statement == ('INSERT INTO gino_users (nickname, type) '
                         'VALUES ($1, $2)')
    assert params == (('1', 'USER'), ('2', 'USER'))
    result = await User.insert().gino.status(dict(nickname='1'),
                                             dict(nickname='2'))
    assert result is None
    assert len(await User.query.gino.all()) == 2


# noinspection PyUnusedLocal
async def test_all(bind):
    result = await User.insert().returning(User.nickname).gino.all(
        dict(nickname='1'), dict(nickname='2'))
    assert result is None
    assert len(await User.query.gino.all()) == 2

    result = await User.insert().gino.all(
        dict(nickname='3'), dict(nickname='4'))
    assert result is None


# noinspection PyUnusedLocal
async def test_first(bind):
    result = await User.insert().returning(User.nickname).gino.first(
        dict(nickname='1'), dict(nickname='2'))
    assert result is None
    assert len(await User.query.gino.all()) == 2

    result = await User.insert().gino.first(
        dict(nickname='3'), dict(nickname='4'))
    assert result is None


# noinspection PyUnusedLocal
async def test_scalar(bind):
    result = await User.insert().returning(User.nickname).gino.scalar(
        dict(nickname='1'), dict(nickname='2'))
    assert result is None
    assert len(await User.query.gino.all()) == 2

    result = await User.insert().gino.scalar(
        dict(nickname='3'), dict(nickname='4'))
    assert result is None
