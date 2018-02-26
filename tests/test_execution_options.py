import pytest

from .models import db, User

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
