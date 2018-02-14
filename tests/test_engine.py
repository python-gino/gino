import pytest

import gino

from .models import DB_ARGS

pytestmark = pytest.mark.asyncio


async def test_create():
    await gino.create_engine(
        'asyncpg://{user}:{password}@{host}:{port}/{database}'.format(
            **DB_ARGS))
