import pytest

import asyncpg
import sqlalchemy as sa
from sqlalchemy.exc import ObjectNotExecutableError

pytestmark = pytest.mark.asyncio


async def test_basic(engine):
    # noinspection PyProtectedMember
    init_size = engine._dialect._pool._queue.qsize()
    async with engine.acquire() as conn:
        assert isinstance(conn.raw_connection, asyncpg.Connection)
        print(await conn.scalar('select now()'))
        print(await conn.scalar(sa.text('select now()')))
    # noinspection PyProtectedMember
    assert init_size == engine._dialect._pool._queue.qsize()


async def test_not_executable(engine):
    async with engine.acquire() as conn:
        with pytest.raises(ObjectNotExecutableError):
            await conn.first(object())
