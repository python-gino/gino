from inspect import iscoroutinefunction

import pytest
import trio_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

import gino
import sql_postgresql_trio as main


@pytest.fixture
async def clean_up():
    async with trio_asyncio.open_loop() as loop:
        try:
            yield

            async with gino.create_engine(main.url) as engine:
                async with engine.connect() as conn:
                    try:
                        await conn.execute(text("DROP TABLE sql_users"))
                    except DBAPIError:
                        pass
        finally:
            await loop.stop().wait()


@pytest.mark.trio
@pytest.mark.parametrize(
    "method",
    [
        method
        for method in dir(main)
        if not method.startswith("_") and iscoroutinefunction(getattr(main, method))
    ],
)
async def test(clean_up, method):
    await getattr(main, method)()
