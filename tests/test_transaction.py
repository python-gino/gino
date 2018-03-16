import pytest

from .models import db, User, qsize

pytestmark = pytest.mark.asyncio


async def _init(bind):
    from .test_crud import test_create
    u = await test_create(bind)

    def get_name():
        return User.select('nickname').where(User.id == u.id).gino.scalar()

    return u, get_name


async def test_connection_ctx(bind, mocker):
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
        mocker.patch(
            'asyncpg.transaction.Transaction.commit').side_effect = IndexError
        with pytest.raises(IndexError):
            await tx.__aexit__(None, None, None)
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
    from asyncpg.transaction import Transaction
    init_size = qsize(bind)
    async with db.acquire() as conn:
        async with db.transaction() as tx:
            assert tx.connection.raw_connection is conn.raw_connection
            assert isinstance(tx.raw_transaction, Transaction)
            async with db.transaction() as tx2:
                assert tx2.connection.raw_connection is conn.raw_connection
            async with db.transaction(reuse=False) as tx2:
                assert tx2.connection.raw_connection is not conn.raw_connection
        async with db.transaction(reuse=False) as tx:
            assert tx.connection.raw_connection is not conn.raw_connection
            async with db.transaction() as tx2:
                assert (tx2.connection.raw_connection is
                        tx.connection.raw_connection)
            async with db.transaction(reuse=False) as tx2:
                assert tx2.connection.raw_connection is not conn.raw_connection
                assert (tx2.connection.raw_connection is not
                        tx.connection.raw_connection)
    with pytest.raises(ValueError, match='already released'):
        await conn.release()
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
        with pytest.raises(AssertionError, match='Illegal in managed mode'):
            await tx.commit()
        await tx.raise_commit()
        assert False, 'Should not reach here'

    async with engine.transaction() as tx:
        with pytest.raises(AssertionError, match='Illegal in managed mode'):
            await tx.rollback()
        await tx.raise_rollback()
        assert False, 'Should not reach here'


async def test_base_exception(engine):
    async with engine.transaction() as tx:
        # noinspection PyBroadException
        try:
            await tx.raise_commit()
        except Exception:
            assert False, 'Should not reach here'
        assert False, 'Should not reach here'
