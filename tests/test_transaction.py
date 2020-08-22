import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from gino.engine import AsyncEngine


async def test_connection_ctx_commit(
    db_val, engine: AsyncEngine, get_db_val_sql, incr_db_val_sql
):
    assert await engine.scalar(get_db_val_sql) == db_val

    async with engine.connect() as conn:
        async with conn.begin():
            await conn.execute(incr_db_val_sql)

    assert await engine.scalar(get_db_val_sql) == db_val + 1


async def test_connection_ctx_error(
    db_val, engine: AsyncEngine, get_db_val_sql, incr_db_val_sql
):
    assert await engine.scalar(get_db_val_sql) == db_val

    with pytest.raises(ZeroDivisionError):
        async with engine.begin() as conn:
            async with conn.begin():
                await conn.execute(incr_db_val_sql)
                assert await conn.scalar(get_db_val_sql) == db_val + 1
                raise ZeroDivisionError

    assert await engine.scalar(get_db_val_sql) == db_val


async def test_connection_ctx_commit_error(
    db_val, engine: AsyncEngine, get_db_val_sql, incr_db_val_sql, mocker
):
    assert await engine.scalar(get_db_val_sql) == db_val

    async with engine.connect() as conn:
        here = False
        with pytest.raises(DBAPIError):
            async with conn.begin():
                await conn.execute(incr_db_val_sql)
                assert await conn.scalar(get_db_val_sql) == db_val + 1

                async def _commit(self):
                    await conn.scalar(text("SELECT * FROM nonexist"))

                mocker.patch("gino.transaction.AsyncTransaction._commit", _commit)
                here = True
        assert here

        # clean up, and to simulate commit failed
        mocker.stopall()
        assert await conn.scalar(get_db_val_sql) == db_val

    assert await engine.scalar(get_db_val_sql) == db_val


async def test_connection_await_commit(
    db_val, engine: AsyncEngine, get_db_val_sql, incr_db_val_sql
):
    assert await engine.scalar(get_db_val_sql) == db_val

    async with engine.connect() as conn:
        tx = await conn.begin()
        await conn.execute(incr_db_val_sql)
        await tx.commit()

    assert await engine.scalar(get_db_val_sql) == db_val + 1


async def test_connection_await_rollback(
    db_val, engine: AsyncEngine, get_db_val_sql, incr_db_val_sql
):
    assert await engine.scalar(get_db_val_sql) == db_val

    async with engine.connect() as conn:
        tx = await conn.begin()
        await conn.execute(incr_db_val_sql)
        assert await conn.scalar(get_db_val_sql) == db_val + 1
        await tx.rollback()

    assert await engine.scalar(get_db_val_sql) == db_val


async def test_connection_await_noop(
    db_val, engine: AsyncEngine, get_db_val_sql, incr_db_val_sql
):
    assert await engine.scalar(get_db_val_sql) == db_val

    # Neither commit nor rollback, should rollback
    async with engine.connect() as conn:
        await conn.begin()
        await conn.execute(incr_db_val_sql)
        assert await conn.scalar(get_db_val_sql) == db_val + 1

    assert await engine.scalar(get_db_val_sql) == db_val


async def test_engine_commit(
    db_val, engine: AsyncEngine, get_db_val_sql, incr_db_val_sql
):
    assert await engine.scalar(get_db_val_sql) == db_val

    async with engine.begin() as conn:
        await conn.execute(incr_db_val_sql)

    assert await engine.scalar(get_db_val_sql) == db_val + 1


async def test_engine_rollback(
    db_val, engine: AsyncEngine, get_db_val_sql, incr_db_val_sql
):
    assert await engine.scalar(get_db_val_sql) == db_val

    with pytest.raises(ZeroDivisionError):
        async with engine.begin() as conn:
            await conn.execute(incr_db_val_sql)
            assert await conn.scalar(get_db_val_sql) == db_val + 1
            raise ZeroDivisionError

    assert await engine.scalar(get_db_val_sql) == db_val


async def test_begin_failed(engine, mocker):
    mocker.patch(
        "gino.transaction.AsyncTransaction._begin"
    ).side_effect = ZeroDivisionError
    checkedin = engine.pool.checkedin()
    with pytest.raises(ZeroDivisionError):
        async with engine.transaction():
            pass  # pragma: no cover
    assert checkedin == engine.pool.checkedin()


async def test_commit_failed(engine, mocker):
    mocker.patch(
        "gino.transaction.AsyncTransaction._commit"
    ).side_effect = ZeroDivisionError
    checkedin = engine.pool.checkedin()
    with pytest.raises(ZeroDivisionError):
        async with engine.transaction():
            pass  # pragma: no cover
    assert checkedin == engine.pool.checkedin()


async def _test_reuse(engine):
    from asyncpg.transaction import Transaction

    init_size = qsize(engine)
    async with db.connect() as conn:
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
                assert tx2.connection.raw_connection is tx.connection.raw_connection
            async with db.transaction(reuse=False) as tx2:
                assert tx2.connection.raw_connection is not conn.raw_connection
                assert tx2.connection.raw_connection is not tx.connection.raw_connection
    with pytest.raises(ValueError, match="already released"):
        await conn.release()
    assert init_size == qsize(engine)


async def test_nested(engine):
    checkedin = engine.pool.checkedin()

    async with engine.begin() as conn:
        async with engine.begin():
            pass

    assert checkedin == engine.pool.checkedin()


# noinspection PyUnreachableCode,PyUnusedLocal
async def test_early_end(engine):
    init_size = qsize(engine)
    u, get_name = await _init(engine)

    assert await get_name() != "ininin"

    async with engine.transaction() as tx:
        async with engine.transaction():
            async with engine.transaction():
                await u.update(nickname="ininin").apply()
                tx.raise_commit()
                assert False, "Should not reach here"
            assert False, "Should not reach here"
        assert False, "Should not reach here"

    assert await get_name() == "ininin"
    assert init_size == qsize(engine)

    async with engine.transaction() as tx:
        async with engine.transaction():
            async with engine.transaction():
                await u.update(nickname="nonono").apply()
                assert await get_name() == "nonono"
                tx.raise_rollback()
                assert False, "Should not reach here"
            assert False, "Should not reach here"
        assert False, "Should not reach here"

    assert await get_name() == "ininin"
    assert init_size == qsize(engine)

    reached = 0

    async with engine.transaction():
        async with engine.transaction() as tx:
            async with engine.transaction():
                await u.update(nickname="nonono").apply()
                assert await get_name() == "nonono"
                tx.raise_rollback()
                assert False, "Should not reach here"
            assert False, "Should not reach here"
        reached += 1
        assert await get_name() == "ininin"

    assert await get_name() == "ininin"
    assert init_size == qsize(engine)
    assert reached == 1

    async with engine.transaction():
        async with engine.transaction() as tx:
            async with engine.transaction():
                await u.update(nickname="nonono").apply()
                assert await get_name() == "nonono"
                tx.raise_commit()
                assert False, "Should not reach here"
            assert False, "Should not reach here"
        reached += 1
        assert await get_name() == "nonono"

    assert await get_name() == "nonono"
    assert init_size == qsize(engine)
    assert reached == 2


# noinspection PyUnreachableCode
async def test_end_raises_in_with(engine):
    async with engine.transaction() as tx:
        with pytest.raises(AssertionError, match="Illegal in managed mode"):
            await tx.commit()
        await tx.raise_commit()
        assert False, "Should not reach here"

    async with engine.transaction() as tx:
        with pytest.raises(AssertionError, match="Illegal in managed mode"):
            await tx.rollback()
        await tx.raise_rollback()
        assert False, "Should not reach here"


async def test_base_exception(engine):
    async with engine.transaction() as tx:
        # noinspection PyBroadException
        try:
            await tx.raise_commit()
        except Exception:
            assert False, "Should not reach here"
        assert False, "Should not reach here"


async def test_no_rollback_on_commit_fail(engine, mocker):
    mocker.patch("asyncpg.transaction.Transaction.commit").side_effect = IndexError
    async with engine.connect() as conn:
        tx = await conn.transaction().__aenter__()
        rollback = mocker.patch.object(tx._tx, "rollback")
        with pytest.raises(IndexError):
            await tx.__aexit__(None, None, None)
        assert not rollback.called
