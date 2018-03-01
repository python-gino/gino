import asyncio
import pytest

from .models import db, User, UserType

pytestmark = pytest.mark.asyncio


async def test(bind):
    await User.create(nickname='test')
    assert isinstance(await User.query.gino.first(), User)
    bind.update_execution_options(return_model=False)
    assert not isinstance(await User.query.gino.first(), User)
    async with db.acquire() as conn:
        assert isinstance(
            await conn.execution_options(return_model=True).first(User.query),
            User)
        assert not isinstance(await User.query.execution_options(
            return_model=False).gino.first(), User)
    assert isinstance(
        await User.query.execution_options(return_model=True).gino.first(),
        User)
    assert not isinstance(await User.query.gino.first(), User)
    bind.update_execution_options(return_model=True)
    assert isinstance(await User.query.gino.first(), User)


# noinspection PyProtectedMember
async def test_compiled_first_not_found(bind):
    async with bind.acquire() as conn:
        with pytest.raises(LookupError, match='No such execution option'):
            result = conn._execute('SELECT NOW()', (), {})
            result.context._compiled_first_opt('nonexist')


# noinspection PyUnusedLocal
async def test_query_ext(bind):
    q = User.query
    assert q.gino.query is q

    u = await User.create(nickname='test')
    assert isinstance(await User.query.gino.first(), User)

    row = await User.query.gino.return_model(False).first()
    assert not isinstance(row, User)
    assert row == (
        u.id, 'test', {'age': 18, 'birthday': '1970-01-01T00:00:00.000000'},
        UserType.USER)

    row = await User.query.gino.model(None).first()
    assert not isinstance(row, User)
    assert row == (
        u.id, 'test', {'age': 18, 'birthday': '1970-01-01T00:00:00.000000'},
        UserType.USER)

    row = await db.select([User.id, User.nickname, User.type]).gino.first()
    assert not isinstance(row, User)
    assert row == (u.id, 'test', UserType.USER)

    user = await db.select(
        [User.id, User.nickname, User.type]).gino.model(User).first()
    assert isinstance(user, User)
    assert user.id is not None
    assert user.nickname == 'test'
    assert user.type == UserType.USER

    with pytest.raises(asyncio.TimeoutError):
        await db.select([db.func.pg_sleep(1), User.id]).gino.timeout(
            0.1).status()
