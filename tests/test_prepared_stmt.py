from datetime import datetime

import pytest
from .models import db, User

pytestmark = pytest.mark.asyncio


async def test_compiled_and_bindparam(bind):
    async with db.acquire() as conn:
        # noinspection PyArgumentList
        ins = await conn.prepare(User.insert().returning(
            *User).execution_options(loader=User))
        users = {}
        for name in '12345':
            u = await ins.first(name=name)
            assert u.nickname == name
            users[u.id] = u
        get = await conn.prepare(
            User.query.where(User.id == db.bindparam('uid')))
        for key in users:
            u = await get.first(uid=key)
            assert u.nickname == users[key].nickname
            assert (await get.all(uid=key))[0].nickname == u.nickname

        assert await get.scalar(uid=-1) is None

        with pytest.raises(ValueError, match='does not support multiple'):
            await get.all([dict(uid=1), dict(uid=2)])

        delete = await conn.prepare(
            User.delete.where(User.nickname == db.bindparam('name')))
        for name in '12345':
            msg = await delete.status(name=name)
            assert msg == 'DELETE 1'


async def test_statement(engine):
    async with engine.acquire() as conn:
        stmt = await conn.prepare('SELECT now()')
        last = None
        for i in range(5):
            now = await stmt.scalar()
            assert isinstance(now, datetime)
            assert last != now
            last = now
