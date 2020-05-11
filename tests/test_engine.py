from datetime import datetime

import pytest

import sqlalchemy

pytestmark = pytest.mark.asyncio


async def test_now(engine):
    async with engine.begin() as conn:
        async with conn.execute(sqlalchemy.text("SELECT now()")) as result:
            rows = await result.all()
    assert isinstance(rows[0][0], datetime)
