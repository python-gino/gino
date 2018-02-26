import pytest

from .models import db, User, qsize

pytestmark = pytest.mark.asyncio


async def _init(bind):
    from .test_basic import test_create
    u = await test_create(bind)

    def get_name():
        return User.select('nickname').where(User.id == u.id).gino.scalar()
    return u, get_name


async def test_connection_ctx(bind):
    init_size = qsize(bind)
    u, get_name = await _init(bind)

    assert await get_name() != 'commit'

    async with bind.acquire() as conn:
        async with conn.transaction():
            await u.update(nickname='commit').apply()
    assert await get_name() == 'commit'

    with pytest.raises(ZeroDivisionError):
        async with bind.acquire() as conn:
            async with conn.transaction():
                await u.update(nickname='rollback').apply()
                assert await get_name() == 'rollback'
                raise ZeroDivisionError

    assert await get_name() == 'commit'

    async with bind.acquire() as conn:
        tx = await conn.transaction().__aenter__()
        await u.update(nickname='rollback').apply()
        assert await get_name() == 'rollback'
        with pytest.raises(IndexError):
            await tx.__aexit__()
        assert await get_name() == 'commit'
    assert await get_name() == 'commit'

    assert init_size == qsize(bind)


async def test_connection_await(bind):
    init_size = qsize(bind)
    u, get_name = await _init(bind)

    assert await get_name() != 'commit'

    async with bind.acquire() as conn:
        tx = await conn.transaction()
        await u.update(nickname='commit').apply()
        await tx.commit()
    assert await get_name() == 'commit'

    async with bind.acquire() as conn:
        tx = await conn.transaction()
        await u.update(nickname='rollback').apply()
        assert await get_name() == 'rollback'
        await tx.rollback()

    assert await get_name() == 'commit'

    # Neither commit nor rollback, should rollback
    async with bind.acquire() as conn:
        await conn.transaction()
        await u.update(nickname='rollback').apply()
        assert await get_name() == 'rollback'

    assert await get_name() == 'commit'

    assert init_size == qsize(bind)


async def test_engine(bind):
    init_size = qsize(bind)
    u, get_name = await _init(bind)

    assert await get_name() != 'commit'

    async with bind.transaction():
        await u.update(nickname='commit').apply()
    assert await get_name() == 'commit'

    with pytest.raises(ZeroDivisionError):
        async with bind.transaction():
            await u.update(nickname='rollback').apply()
            raise ZeroDivisionError
    assert await get_name() == 'commit'
    assert init_size == qsize(bind)


async def test_begin_failed(bind, mocker):
    from asyncpg.transaction import Transaction
    init_size = qsize(bind)
    mocker.patch('asyncpg.transaction.Transaction.start')
    Transaction.start.side_effect = ZeroDivisionError
    with pytest.raises(ZeroDivisionError):
        async with bind.transaction():
            pass  # pragma: no cover
    assert init_size == qsize(bind)


async def test_commit_failed(bind, mocker):
    from asyncpg.transaction import Transaction
    init_size = qsize(bind)
    mocker.patch('asyncpg.transaction.Transaction._Transaction__commit')
    # noinspection PyUnresolvedReferences,PyProtectedMember
    Transaction._Transaction__commit.side_effect = ZeroDivisionError
    with pytest.raises(ZeroDivisionError):
        async with bind.transaction():
            pass
    assert init_size == qsize(bind)


async def test_reuse(bind):
    init_size = qsize(bind)
    async with db.acquire() as conn:
        async with db.transaction() as tx:
            assert tx.connection is conn
            assert tx.transaction is None
            async with db.transaction() as tx2:
                assert tx2.connection is conn
            async with db.transaction(reuse=False) as tx2:
                assert tx2.connection is not conn
        async with db.transaction(reuse=False) as tx:
            assert tx.connection is not conn
            async with db.transaction() as tx2:
                assert tx2.connection is tx.connection
            async with db.transaction(reuse=False) as tx2:
                assert tx2.connection is not conn
                assert tx2.connection is not tx.connection
    assert init_size == qsize(bind)


async def test_nested(bind):
    init_size = qsize(bind)
    u, get_name = await _init(bind)

    name = await get_name()
    assert u.nickname == name

    async with bind.transaction():
        await u.update(nickname='first').apply()
        async with bind.transaction():
            pass

    assert init_size == qsize(bind)


# noinspection PyUnreachableCode,PyUnusedLocal
async def test_early_end(bind):
    init_size = qsize(bind)
    u, get_name = await _init(bind)

    assert await get_name() != 'ininin'

    async with bind.transaction() as tx:
        async with bind.transaction():
            async with bind.transaction():
                await u.update(nickname='ininin').apply()
                tx.raise_commit()
                assert False, 'Should not reach here'
            assert False, 'Should not reach here'
        assert False, 'Should not reach here'

    assert await get_name() == 'ininin'
    assert init_size == qsize(bind)

    async with bind.transaction() as tx:
        async with bind.transaction():
            async with bind.transaction():
                await u.update(nickname='nonono').apply()
                assert await get_name() == 'nonono'
                tx.raise_rollback()
                assert False, 'Should not reach here'
            assert False, 'Should not reach here'
        assert False, 'Should not reach here'

    assert await get_name() == 'ininin'
    assert init_size == qsize(bind)

    reached = 0

    async with bind.transaction():
        async with bind.transaction() as tx:
            async with bind.transaction():
                await u.update(nickname='nonono').apply()
                assert await get_name() == 'nonono'
                tx.raise_rollback()
                assert False, 'Should not reach here'
            assert False, 'Should not reach here'
        reached += 1
        assert await get_name() == 'ininin'

    assert await get_name() == 'ininin'
    assert init_size == qsize(bind)
    assert reached == 1

    async with bind.transaction():
        async with bind.transaction() as tx:
            async with bind.transaction():
                await u.update(nickname='nonono').apply()
                assert await get_name() == 'nonono'
                tx.raise_commit()
                assert False, 'Should not reach here'
            assert False, 'Should not reach here'
        reached += 1
        assert await get_name() == 'nonono'

    assert await get_name() == 'nonono'
    assert init_size == qsize(bind)
    assert reached == 2


# noinspection PyUnreachableCode
async def test_end_raises_in_with(engine):
    async with engine.transaction() as tx:
        await tx.commit()
        assert False, 'Should not reach here'

    async with engine.transaction() as tx:
        await tx.rollback()
        assert False, 'Should not reach here'
