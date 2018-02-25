import logging
import random
from datetime import datetime

import asyncpg
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import ObjectNotExecutableError
from asyncpg.exceptions import InvalidCatalogNameError

from .models import db, User, UserType, Friendship, ASYNCPG_URL, qsize

pytestmark = pytest.mark.asyncio


async def test_basic(engine):
    init_size = qsize(engine)
    async with engine.acquire() as conn:
        assert isinstance(conn.raw_connection, asyncpg.Connection)
    assert init_size == qsize(engine)
    assert isinstance(await engine.scalar('select now()'), datetime)
    assert isinstance(await engine.scalar(sa.text('select now()')), datetime)
    assert isinstance((await engine.first('select now()'))[0], datetime)
    assert isinstance((await engine.all('select now()'))[0][0], datetime)
    status, result = await engine.status('select now()')
    assert status == 'SELECT 1'
    assert isinstance(result[0][0], datetime)
    with pytest.raises(ObjectNotExecutableError):
        await engine.all(object())


async def test_create(engine):
    nickname = 'test_create_{}'.format(random.random())
    u = await User.create(bind=engine, nickname=nickname,
                          type=UserType.USER)
    assert u.id is not None
    assert u.nickname == nickname
    assert u.type == UserType.USER
    return u


async def test_get(engine):
    u1 = await test_create(engine)
    u2 = await User.get(u1.id, bind=engine)
    assert u1.id == u2.id
    assert u1.nickname == u2.nickname
    assert u1 is not u2


async def test_get_multiple_primary_key(engine):
    u1 = await test_create(engine)
    u2 = await test_create(engine)
    await Friendship.create(bind=engine, my_id=u1.id, friend_id=u2.id)
    f = await Friendship.get((u1.id, u2.id), bind=engine)
    assert f
    assert f.my_id == u1.id
    assert f.friend_id == u2.id


async def test_connection_as_bind(engine):
    async with engine.acquire() as conn:
        await test_get(conn)


async def test_update(engine, random_name):
    u1 = await test_create(engine)
    await u1.update(nickname=random_name).apply(bind=engine)
    u2 = await User.get(u1.id, bind=engine)
    assert u2.nickname == random_name


async def test_update_multiple_primary_key(engine):
    u1 = await test_create(engine)
    u2 = await test_create(engine)
    u3 = await test_create(engine)
    await Friendship.create(bind=engine, my_id=u1.id, friend_id=u2.id)
    f = await Friendship.get((u1.id, u2.id), bind=engine)
    await f.update(my_id=u2.id, friend_id=u3.id).apply(bind=engine)
    f2 = await Friendship.get((u2.id, u3.id), bind=engine)
    assert f2


async def test_delete(engine):
    u1 = await test_create(engine)
    await u1.delete(bind=engine)
    u2 = await User.get(u1.id, bind=engine)
    assert not u2


async def test_delete_multiple_primary_key(engine):
    u1 = await test_create(engine)
    u2 = await test_create(engine)
    f = await Friendship.create(bind=engine, my_id=u1.id, friend_id=u2.id)
    await f.delete(bind=engine)
    f2 = await Friendship.get((u1.id, u2.id), bind=engine)
    assert not f2


async def test_issue_79():
    import gino
    db_ = gino.Gino()
    e = await db_.create_engine('asyncpg:///non_exist?min_size=0')
    with pytest.raises(InvalidCatalogNameError):
        async with e.acquire():
            pass  # pragma: no cover
    # noinspection PyProtectedMember
    assert len(e._ctx.get([])) == 0


async def test_reuse(engine):
    init_size = qsize(engine)
    async with engine.acquire(reuse=True) as conn1:
        assert qsize(engine) == init_size - 1
        async with engine.acquire(reuse=True) as conn2:
            assert qsize(engine) == init_size - 1
            assert conn1 is conn2
        assert qsize(engine) == init_size - 1
    assert qsize(engine) == init_size

    async with engine.acquire(reuse=False) as conn1:
        assert qsize(engine) == init_size - 1
        async with engine.acquire(reuse=True) as conn2:
            assert qsize(engine) == init_size - 1
            assert conn1 is conn2
        assert qsize(engine) == init_size - 1
    assert qsize(engine) == init_size

    async with engine.acquire(reuse=True) as conn1:
        assert qsize(engine) == init_size - 1
        async with engine.acquire(reuse=False) as conn2:
            assert qsize(engine) == init_size - 2
            assert conn1 is not conn2
        assert qsize(engine) == init_size - 1
    assert qsize(engine) == init_size

    async with engine.acquire(reuse=False) as conn1:
        assert qsize(engine) == init_size - 1
        async with engine.acquire(reuse=False) as conn2:
            assert qsize(engine) == init_size - 2
            assert conn1 is not conn2
        assert qsize(engine) == init_size - 1
    assert qsize(engine) == init_size

    async with engine.acquire(reuse=False) as conn1:
        assert qsize(engine) == init_size - 1
        async with engine.acquire(reuse=True) as conn2:
            assert qsize(engine) == init_size - 1
            assert conn1 is conn2
            async with engine.acquire(reuse=False) as conn3:
                assert qsize(engine) == init_size - 2
                assert conn1 is not conn3
                async with engine.acquire(reuse=True) as conn4:
                    assert qsize(engine) == init_size - 2
                    assert conn3 is conn4
                assert qsize(engine) == init_size - 2
            assert qsize(engine) == init_size - 1
        assert qsize(engine) == init_size - 1
    assert qsize(engine) == init_size


async def test_no_reuse(mocker):
    class NotExist:
        # noinspection PyPep8Naming
        @property
        def ContextVar(self):
            raise ImportError

    mocker.patch.dict('sys.modules', {'contextvars': NotExist(),
                                      'aiocontextvars': NotExist()})

    import gino
    engine = await gino.create_engine(ASYNCPG_URL)
    ctx = getattr(engine, '_ctx')
    assert ctx.name == 'gino'
    assert ctx.default is None
    with pytest.raises(LookupError):
        ctx.delete()

    init_size = qsize(engine)
    async with engine.acquire(reuse=True) as conn1:
        assert qsize(engine) == init_size - 1
        async with engine.acquire(reuse=True) as conn2:
            assert qsize(engine) == init_size - 2
            assert conn1 is not conn2
        assert qsize(engine) == init_size - 1
    assert qsize(engine) == init_size


async def test_compile(engine):
    stmt, params = engine.compile(User.query.where(User.id == 3))
    assert params[0] == 3


async def test_logging(mocker):
    import gino
    mocker.patch('logging.Logger._log')
    sql = 'SELECT NOW() AS test_logging'

    e = await gino.create_engine(ASYNCPG_URL, echo=False)
    await e.scalar(sql)
    await e.close()
    # noinspection PyProtectedMember,PyUnresolvedReferences
    logging.Logger._log.assert_not_called()

    e = await gino.create_engine(ASYNCPG_URL, echo=True)
    await e.scalar(sql)
    await e.close()
    # noinspection PyProtectedMember,PyUnresolvedReferences
    logging.Logger._log.assert_any_call(logging.INFO, sql, ())


async def test_set_isolation_level():
    import gino
    with pytest.raises(sa.exc.ArgumentError):
        await gino.create_engine(ASYNCPG_URL, isolation_level='non')
    e = await gino.create_engine(ASYNCPG_URL,
                                 isolation_level='READ_UNCOMMITTED')
    async with e.acquire() as conn:
        assert await e.dialect.get_isolation_level(
            conn.raw_connection) == 'READ UNCOMMITTED'
    async with e.transaction(isolation='serializable') as tx:
        assert await e.dialect.get_isolation_level(
            tx.connection.raw_connection) == 'SERIALIZABLE'


async def test_too_many_engine_args():
    import gino
    with pytest.raises(TypeError):
        await gino.create_engine(ASYNCPG_URL, non_exist=None)


# noinspection PyUnusedLocal
async def test_scalar_return_none(bind):
    assert await User.query.where(
        User.nickname == 'nonexist').gino.scalar() is None


async def test_execute_many(bind):
    statement, params = db.compile(User.insert(),
                                   [dict(nickname='1'), dict(nickname='2')])
    assert statement == ('INSERT INTO gino_users (nickname, type) '
                         'VALUES ($1, $2)')
    assert params == (('1', 'USER'), ('2', 'USER'))
    await User.insert().gino.status(dict(nickname='1'), dict(nickname='2'))
    assert len(await User.query.gino.all()) == 2


async def test_asyncpg_0120(bind, mocker):
    assert await bind.first('rollback') is None
    mocker.patch('asyncpg.prepared_stmt.'
                 'PreparedStatement.get_attributes').side_effect = TypeError
    assert await bind.first('rollback') is None
