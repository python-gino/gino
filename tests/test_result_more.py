import random

import pytest

from gino.engine import AsyncConnection

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def more(add_db_val_sql, db_val, conn: AsyncConnection):
    num = random.randint(128, 256)
    await conn.execute(add_db_val_sql, [dict(value=i) for i in range(num)])
    return num


async def test_fetchmany_basic(more, con: AsyncConnection, get_db_val_sql):
    rows = await con.execute(get_db_val_sql).fetchmany(64)
    assert sum(row[0] for row in rows) == sum(range(64))


async def test_fetchmany_basic_yield_per(more, con: AsyncConnection, get_db_val_sql):
    rows = await con.execute(get_db_val_sql).yield_per(64).fetchmany()
    assert sum(row[0] for row in rows) == sum(range(64))


async def test_fetchmany_in_ctx(db_val, more, con: AsyncConnection, get_db_val_sql):
    value = 0
    async with con.execute(get_db_val_sql) as result:
        while True:
            rows = await result.fetchmany(random.randint(64, 128))
            if not rows:
                break
            value += sum(row[0] for row in rows)
    assert value == sum(range(more)) + db_val


async def test_fetchmany_in_ctx_yield_per(
    db_val, more, con: AsyncConnection, get_db_val_sql
):
    value = 0
    async with con.execute(get_db_val_sql).yield_per(random.randint(64, 128)) as result:
        while True:
            rows = await result.fetchmany()
            if not rows:
                break
            value += sum(row[0] for row in rows)
    assert value == sum(range(more)) + db_val


@pytest.mark.parametrize("yield_per", [None, 32])
async def test_mixed_fetch(
    db_val, more, con: AsyncConnection, get_db_val_sql, yield_per
):
    value = 0

    async with con.execute(get_db_val_sql).yield_per(yield_per) as result:
        for i in range(16):
            row = await result.fetchone()
            value += row[0]

        for i in range(2):
            rows = await result.fetchmany(32)
            value += sum(row[0] for row in rows)

        for i in range(20):
            row = await result.fetchone()
            value += row[0]

        rows = await result.fetchall()
        value += sum(row[0] for row in rows)

        assert (await result.fetchone()) is None
        assert len(await result.fetchmany()) == 0
        assert len(await result.fetchmany(128)) == 0
        assert len(await result.fetchall()) == 0

    assert value == sum(range(more)) + db_val


@pytest.mark.parametrize("yield_per", [None, 32])
async def test_iter_basic(
    db_val, more, con: AsyncConnection, get_db_val_sql, yield_per
):
    value = 0
    async for row in con.execute(get_db_val_sql).yield_per(yield_per):
        value += row[0]
    assert value == sum(range(more)) + db_val


async def _test_iter_nested(result):
    value = 0
    async for row1 in result:
        value += row1[0]
        if 10 < value < 100:
            async for row2 in result:
                value += row2[0]
                if value > 100:
                    break
    return value


@pytest.mark.parametrize("yield_per", [None, 32])
async def test_iter_nested(
    db_val, more, con: AsyncConnection, get_db_val_sql, yield_per
):
    result = con.execute(get_db_val_sql).yield_per(yield_per)
    value = await _test_iter_nested(result)
    assert value == sum(range(more)) + db_val


@pytest.mark.parametrize("yield_per", [None, 32])
async def test_iter_nested_in_ctx(
    db_val, more, con: AsyncConnection, get_db_val_sql, yield_per
):
    async with con.execute(get_db_val_sql).yield_per(yield_per) as result:
        value = await _test_iter_nested(result)
        assert value == sum(range(more)) + db_val
