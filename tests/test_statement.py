import pytest

from .models import db, DB_ARGS, User

pytestmark = pytest.mark.asyncio


async def test_anonymous(engine):
    async with db.create_pool(**DB_ARGS, statement_cache_size=0) as pool:
        async with pool.acquire() as conn:
            await conn.first(User.query.where(User.id == 1))
            # anonymous statement should not be closed
            await conn.first(User.query.where(User.id == 1))
