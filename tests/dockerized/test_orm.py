from tests.dockerized.models import User, Post
import pytest

pytestmark = pytest.mark.asyncio


async def test_create_two_users(db_schema):
    u1 = await User.create(username='Alice')
    u2 = await User.create(username='Bob')
    all_users = await User.query.gino.all()
    assert len(all_users) == 2
