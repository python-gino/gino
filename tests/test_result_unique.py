import pytest
from sqlalchemy.exc import MultipleResultsFound

from gino.engine import AsyncConnection

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def duplicate(db_val, conn: AsyncConnection, add_db_val_sql):
    await conn.execute(add_db_val_sql, [dict(value=db_val)] * 3)


@pytest.fixture
async def duplicate1(db_val, duplicate, conn: AsyncConnection, add_db_val_sql):
    await conn.execute(add_db_val_sql, [dict(value=db_val + 1)] * 5)


async def test_unique_iter(db_val, duplicate1, con: AsyncConnection, get_db_val_sql):
    value = 0
    async for row in con.execute(get_db_val_sql).unique():
        value += row[0]
    assert value == db_val * 2 + 1


async def test_unique_all(db_val, duplicate1, con: AsyncConnection, get_db_val_sql):
    value = 0
    for row in await con.execute(get_db_val_sql).unique().all():
        value += row[0]
    assert value == db_val * 2 + 1


@pytest.mark.parametrize("size", [None, 1, 2, 3, 10])
async def test_unique_fetchmany(
    db_val, duplicate1, con: AsyncConnection, get_db_val_sql, size
):
    value = 0
    for row in await con.execute(get_db_val_sql).unique().fetchmany(size):
        value += row[0]
    if size == 1:
        assert value == db_val
    else:
        assert value == db_val * 2 + 1


async def test_unique_fetchone(
    db_val, duplicate1, con: AsyncConnection, get_db_val_sql
):
    value = 0
    async with con.execute(get_db_val_sql).unique() as result:
        while True:
            row = await result.fetchone()
            if not row:
                break
            value += row[0]
    assert value == db_val * 2 + 1


async def test_unique_first(db_val, duplicate1, con: AsyncConnection, get_db_val_sql):
    row = await con.execute(get_db_val_sql).unique().first()
    assert row[0] == db_val


async def test_unique_one_or_none(
    db_val, duplicate, con: AsyncConnection, get_db_val_sql
):
    row = await con.execute(get_db_val_sql).unique().one_or_none()
    assert row[0] == db_val


async def test_unique_one_or_none_multiple(
    db_val, duplicate1, con: AsyncConnection, get_db_val_sql
):
    with pytest.raises(MultipleResultsFound):
        await con.execute(get_db_val_sql).unique().one_or_none()
