from datetime import datetime

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
    # noinspection PyProtectedMember
    assert init_size == engine._dialect._pool._queue.qsize()
    assert isinstance(await engine.scalar('select now()'), datetime)
    assert isinstance(await engine.scalar(sa.text('select now()')), datetime)
    assert isinstance((await engine.first('select now()'))[0], datetime)
    assert isinstance((await engine.all('select now()'))[0][0], datetime)
    status, result = await engine.status('select now()')
    assert status == 'SELECT 1'
    assert isinstance(result[0][0], datetime)
    with pytest.raises(ObjectNotExecutableError):
        await engine.all(object())
