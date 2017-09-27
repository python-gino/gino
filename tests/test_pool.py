import pytest
from asyncpg.exceptions import InvalidCatalogNameError

from gino import Gino, get_local

pytestmark = pytest.mark.asyncio


# noinspection PyUnusedLocal
async def test_issue_79(task_local):
    db = Gino()
    pool = await db.create_pool('postgresql:///non_exist', min_size=0)
    with pytest.raises(InvalidCatalogNameError):
        await pool.acquire()
    assert len(get_local().get('connection_stack', [])) == 0
