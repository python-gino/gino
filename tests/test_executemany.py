import pytest

from .models import User

pytestmark = pytest.mark.asyncio


# noinspection PyUnusedLocal
async def test_create_many(pool):
    count = 5
    rows = [dict(id=i + 1, nickname=f'test_{i + 1}') for i in range(count)]
    async with pool.acquire() as conn:
        await User.create_many(rows, bind=conn)
    query = User.select('id', 'nickname')
    users = [await User.get(i + 1, bind=pool) for i in range(count)]
    users = [u for u in users if u is not None]
    assert len(users) == count


async def test_execute_many(pool):
    count = 5
    rows = [dict(id=i + 1, nickname=f'test_{i + 1}') for i in range(count)]
    await pool.executemany(User.__table__.insert(), rows)
    users = [await User.get(i + 1, bind=pool) for i in range(count)]
    users = [u for u in users if u is not None]
    assert len(users) == count
