import pytest

from .models import User

pytestmark = pytest.mark.asyncio


# noinspection PyUnusedLocal
async def test_create_many(pool):
    count = 4
    rows = [dict(id=i + 1, nickname=f'test_{i + 1}') for i in range(4)]
    async with pool.acquire() as conn:
        await User.create_many(rows, bind=conn)
    query = User.select('id', 'nickname')
    users = [await User.get(i + 1, bind=pool) for i in range(4)]
    assert len(users) == count
