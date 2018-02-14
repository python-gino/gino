import pytest

import asyncpg
import gino

from .models import DB_ARGS

pytestmark = pytest.mark.asyncio


async def test_basic():
    e = await gino.create_engine(
        'asyncpg://{user}:{password}@{host}:{port}/{database}'.format(
            **DB_ARGS))
    init_size = e._dialect._pool._queue.qsize()
    async with e.acquire() as conn:
        assert isinstance(conn.raw_connection, asyncpg.Connection)
    assert init_size == e._dialect._pool._queue.qsize()
