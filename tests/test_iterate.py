import pytest

from .models import db, User

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def names(sa_engine):
    rv = {'11', '22', '33'}
    sa_engine.execute(User.__table__.insert(),
                      [dict(nickname=name) for name in rv])
    yield rv
    sa_engine.execute('DELETE FROM gino_users')


# noinspection PyUnusedLocal,PyShadowingNames
async def test_bind(bind, names):
    with pytest.raises(ValueError, match='No Connection in context'):
        async for u in User.query.gino.iterate():
            assert False, 'Should not reach here'
    with pytest.raises(ValueError, match='No Connection in context'):
        await User.query.gino.iterate()
    with pytest.raises(ValueError, match='No Connection in context'):
        await db.iterate(User.query)

    result = set()
    async with bind.transaction():
        async for u in User.query.gino.iterate():
            result.add(u.nickname)
    assert names == result

    result = set()
    async with bind.transaction():
        async for u in db.iterate(User.query):
            result.add(u.nickname)
    assert names == result

    result = set()
    async with bind.transaction():
        cursor = await User.query.gino.iterate()
        result.add((await cursor.next()).nickname)
        assert names != result
        result.update([u.nickname for u in await cursor.many(1)])
        assert names != result
        result.update([u.nickname for u in await cursor.many(2)])
        assert names == result
        result.update([u.nickname for u in await cursor.many(2)])
        assert names == result
        assert await cursor.next() is None

    with pytest.raises(ValueError, match='too many multiparams'):
        async with bind.transaction():
            await db.iterate(User.insert().returning(User.nickname), [
                dict(nickname='444'),
                dict(nickname='555'),
                dict(nickname='666'),
            ])

    result = set()
    async with bind.transaction():
        cursor = await User.query.gino.iterate()
        await cursor.forward(1)
        result.add((await cursor.next()).nickname)
        assert names != result
        result.update([u.nickname for u in await cursor.many(1)])
        assert names != result
        result.update([u.nickname for u in await cursor.many(2)])
        assert names != result
        assert await cursor.next() is None


# noinspection PyUnusedLocal,PyShadowingNames
async def test_basic(engine, names):
    result = set()
    async with engine.transaction() as tx:
        with pytest.raises(AttributeError, match='iterate'):
            await db.iterate(User.query)
        result = set()
        async for u in tx.connection.iterate(User.query):
            result.add(u.nickname)
        async for u in tx.connection.execution_options(
                timeout=1).iterate(User.query):
            result.add(u.nickname)
        assert names == result

        result = set()
        cursor = await tx.connection.iterate(User.query)
        result.update([u.nickname for u in await cursor.many(2)])
        assert names != result
        result.update([u.nickname for u in await cursor.many(2)])
        assert names == result
