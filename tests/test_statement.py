import pytest

from .models import PG_URL, User

pytestmark = pytest.mark.asyncio


async def test_anonymous(sa_engine):
    import gino
    e = await gino.create_engine(PG_URL, statement_cache_size=0)
    async with e.acquire() as conn:
        # noinspection PyProtectedMember
        assert conn.raw_connection._stmt_cache.get_max_size() == 0
        await conn.first(User.query.where(User.id == 1))
        # anonymous statement should not be closed
        await conn.first(User.query.where(User.id == 1))
    await e.close()
