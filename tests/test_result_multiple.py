import pytest

from gino.engine import AsyncConnection
from gino.errors import InterfaceError


@pytest.fixture(params=["all", "fetchmany"])
def method(request):
    return request.param


async def test_multiple_basic(db_val, con: AsyncConnection, get_db_val_sql, method):
    rows = await getattr(con.execute(get_db_val_sql), method)()
    assert len(rows) == 1
    assert rows[0][0] == db_val


async def test_multiple_empty(db_val, con: AsyncConnection, find_db_val_sql, method):
    rows = await getattr(
        con.execute(find_db_val_sql.bindparams(value=db_val + 1)), method
    )()
    assert len(rows) == 0


async def test_multiple_multiple(db_val, con: AsyncConnection, get_db_val_sql, method):
    result = con.execute(get_db_val_sql)
    rows = await getattr(result, method)()
    assert len(rows) == 1
    assert rows[0][0] == db_val
    with pytest.raises(InterfaceError):
        await getattr(result, method)()


async def test_multiple_in_ctx(db_val, con: AsyncConnection, get_db_val_sql, method):
    async with con.execute(get_db_val_sql) as result:
        rows = await getattr(result, method)()
        assert len(rows) == 1
        assert rows[0][0] == db_val

        rows = await getattr(result, method)()
        assert len(rows) == 0


async def test_multiple_in_ctx_empty(
    db_val, con: AsyncConnection, find_db_val_sql, method
):
    async with con.execute(find_db_val_sql.bindparams(value=db_val + 1)) as result:
        rows = await getattr(result, method)()
        assert len(rows) == 0
