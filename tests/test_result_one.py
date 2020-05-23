import pytest
from sqlalchemy.exc import MultipleResultsFound, NoResultFound, InvalidRequestError

from gino.engine import AsyncConnection


@pytest.fixture
async def one_more(add_db_val_sql, db_val, con: AsyncConnection):
    await con.execute(add_db_val_sql, dict(value=db_val + 1))


async def test_first(db_val, one_more, con: AsyncConnection, get_db_val_sql):
    assert (await con.execute(get_db_val_sql).first())[0] == db_val

    async with con.execute(get_db_val_sql) as result:
        with pytest.raises(InvalidRequestError):
            await result.first()


async def test_one_or_none(
    db_val, con: AsyncConnection, get_db_val_sql, find_db_val_sql
):
    assert (await con.execute(get_db_val_sql).one_or_none())[0] == db_val
    assert (
        await con.execute(find_db_val_sql, dict(value=db_val + 1)).one_or_none()
    ) is None

    async with con.execute(get_db_val_sql) as result:
        with pytest.raises(InvalidRequestError):
            await result.one_or_none()


async def test_one_or_none_one_more(
    db_val, one_more, con: AsyncConnection, get_db_val_sql
):
    with pytest.raises(MultipleResultsFound):
        await con.execute(get_db_val_sql).one_or_none()

    async with con.execute(get_db_val_sql) as result:
        with pytest.raises(InvalidRequestError):
            await result.one_or_none()


async def test_one(db_val, con: AsyncConnection, get_db_val_sql, find_db_val_sql):
    assert (await con.execute(get_db_val_sql).one())[0] == db_val
    with pytest.raises(NoResultFound):
        await con.execute(find_db_val_sql, dict(value=db_val + 1)).one()

    async with con.execute(get_db_val_sql) as result:
        with pytest.raises(InvalidRequestError):
            await result.one()


async def test_scalar_basic(db_val, con: AsyncConnection, get_db_val_sql):
    assert (await con.execute(get_db_val_sql).scalar()) == db_val


async def test_scalar_in_ctx(db_val, con: AsyncConnection, get_db_val_sql):
    async with con.execute(get_db_val_sql) as result:
        with pytest.raises(InvalidRequestError):
            await result.scalar()


async def test_scalar_none(db_val, con: AsyncConnection, find_db_val_sql):
    assert (await con.execute(find_db_val_sql, dict(value=db_val + 1)).scalar()) is None
