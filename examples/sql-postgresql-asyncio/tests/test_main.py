from inspect import iscoroutinefunction

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

import gino
import sql_postgresql_asyncio as main


@pytest.fixture(autouse=True)
async def clean_up():
    yield

    async with gino.create_engine(main.url) as engine:
        async with engine.connect() as conn:
            try:
                await conn.execute(text("DROP TABLE sql_users"))
            except DBAPIError:
                pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method",
    [
        method
        for method in dir(main)
        if not method.startswith("_") and iscoroutinefunction(getattr(main, method))
    ],
)
async def test(method):
    await getattr(main, method)()
