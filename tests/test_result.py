import pytest

from gino.engine import AsyncConnection
from gino.errors import InterfaceError


async def test_execute(db_val, con: AsyncConnection, get_db_val_sql, incr_db_val_sql):
    rv = await con.execute(incr_db_val_sql)
    assert rv is None
    assert (await con.scalar(get_db_val_sql)) == db_val + 1


async def test_execute_multiple(
    db_val, con: AsyncConnection, get_db_val_sql, incr_db_val_sql
):
    result = con.execute(incr_db_val_sql)
    await result
    assert (await con.scalar(get_db_val_sql)) == db_val + 1
    with pytest.raises(InterfaceError):
        await result


async def test_execute_in_ctx(
    db_val, con: AsyncConnection, get_db_val_sql, incr_db_val_sql
):
    async with con.execute(incr_db_val_sql):
        pass
    assert (await con.scalar(get_db_val_sql)) == db_val + 1


async def test_execute_nested_ctx(
    db_val, con: AsyncConnection, get_db_val_sql, incr_db_val_sql
):
    result = con.execute(incr_db_val_sql)
    async with result:
        async with result:
            pass
    assert (await con.scalar(get_db_val_sql)) == db_val + 1


async def test_execute_again_in_ctx(
    db_val, con: AsyncConnection, get_db_val_sql, incr_db_val_sql
):
    with pytest.raises(InterfaceError):
        async with con.execute(incr_db_val_sql) as result:
            await result
    assert (await con.scalar(get_db_val_sql)) == db_val + 1


async def test_fetchone_basic(db_val, con: AsyncConnection, get_db_val_sql):
    row = await con.execute(get_db_val_sql).fetchone()
    assert row[0] == db_val


async def test_fetchone_empty(db_val, con: AsyncConnection, find_db_val_sql):
    row = await con.execute(find_db_val_sql.bindparams(value=db_val + 1)).fetchone()
    assert row is None


async def test_fetchone_multiple(db_val, con: AsyncConnection, get_db_val_sql):
    result = con.execute(get_db_val_sql)
    row = await result.fetchone()
    assert row[0] == db_val
    with pytest.raises(InterfaceError):
        await result.fetchone()


async def test_fetchone_in_ctx(db_val, con: AsyncConnection, get_db_val_sql):
    async with con.execute(get_db_val_sql) as result:
        row = await result.fetchone()
        assert row[0] == db_val
        row = await result.fetchone()
        assert row is None


async def test_fetchone_in_ctx_empty(db_val, con: AsyncConnection, find_db_val_sql):
    async with con.execute(find_db_val_sql.bindparams(value=db_val + 1)) as result:
        row = await result.fetchone()
        assert row is None


async def test_iter_non_async(conn: AsyncConnection, get_db_val_sql):
    with pytest.raises(NotImplementedError):
        for row in conn.execute(get_db_val_sql):
            pass

    with pytest.raises(NotImplementedError):
        conn.execute(get_db_val_sql).next()

    with pytest.raises(NotImplementedError):
        next(conn.execute(get_db_val_sql))
