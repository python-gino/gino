import asyncio
import logging
from datetime import datetime

import asyncpg
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import ObjectNotExecutableError
from asyncpg.exceptions import InvalidCatalogNameError

from .models import db, User, PG_URL, qsize

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


async def test_issue_79():
    import gino
    e = await gino.create_engine('postgresql:///non_exist', min_size=0)
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
            assert conn1.raw_connection is conn2.raw_connection
            assert await engine.scalar('select now()')
            assert qsize(engine) == init_size - 1
        assert qsize(engine) == init_size - 1
    assert qsize(engine) == init_size

    async with engine.acquire(reuse=False) as conn1:
        assert qsize(engine) == init_size - 1
        async with engine.acquire(reuse=True) as conn2:
            assert qsize(engine) == init_size - 1
            assert conn1.raw_connection is conn2.raw_connection
        assert qsize(engine) == init_size - 1
    assert qsize(engine) == init_size

    async with engine.acquire(reuse=True) as conn1:
        assert qsize(engine) == init_size - 1
        async with engine.acquire(reuse=False) as conn2:
            assert qsize(engine) == init_size - 2
            assert conn1.raw_connection is not conn2.raw_connection
        assert qsize(engine) == init_size - 1
    assert qsize(engine) == init_size

    async with engine.acquire(reuse=False) as conn1:
        assert qsize(engine) == init_size - 1
        async with engine.acquire(reuse=False) as conn2:
            assert qsize(engine) == init_size - 2
            assert conn1.raw_connection is not conn2.raw_connection
        assert qsize(engine) == init_size - 1
    assert qsize(engine) == init_size

    async with engine.acquire(reuse=False) as conn1:
        assert qsize(engine) == init_size - 1
        async with engine.acquire(reuse=True) as conn2:
            assert qsize(engine) == init_size - 1
            assert conn1.raw_connection is conn2.raw_connection
            async with engine.acquire(reuse=False) as conn3:
                assert qsize(engine) == init_size - 2
                assert conn1.raw_connection is not conn3.raw_connection
                async with engine.acquire(reuse=True) as conn4:
                    assert qsize(engine) == init_size - 2
                    assert conn3.raw_connection is conn4.raw_connection
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
    engine = await gino.create_engine(PG_URL)
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

    e = await gino.create_engine(PG_URL, echo=False)
    await e.scalar(sql)
    await e.close()
    # noinspection PyProtectedMember,PyUnresolvedReferences
    logging.Logger._log.assert_not_called()

    e = await gino.create_engine(PG_URL, echo=True)
    await e.scalar(sql)
    await e.close()
    # noinspection PyProtectedMember,PyUnresolvedReferences
    logging.Logger._log.assert_any_call(logging.INFO, sql, ())


async def test_set_isolation_level():
    import gino
    with pytest.raises(sa.exc.ArgumentError):
        await gino.create_engine(PG_URL, isolation_level='non')
    e = await gino.create_engine(PG_URL,
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
        await gino.create_engine(PG_URL, non_exist=None)


# noinspection PyUnusedLocal
async def test_scalar_return_none(bind):
    assert await User.query.where(
        User.nickname == 'nonexist').gino.scalar() is None


async def test_asyncpg_0120(bind, mocker):
    assert await bind.first('rollback') is None

    orig = getattr(asyncpg.Connection, '_do_execute')

    class Stmt:
        def __init__(self, stmt):
            self._stmt = stmt

        def _get_attributes(self):
            raise TypeError

    async def new(*args, **kwargs):
        result, stmt = await orig(*args, **kwargs)
        return result, Stmt(stmt)

    mocker.patch('asyncpg.Connection._do_execute', new=new)

    assert await bind.first('rollback') is None


async def test_asyncpg_0120_iterate(bind, mocker):
    async with bind.transaction():
        gen = await db.iterate('rollback')
        assert await gen.next() is None

    mocker.patch('asyncpg.prepared_stmt.'
                 'PreparedStatement.get_attributes').side_effect = TypeError

    async with bind.transaction():
        gen = await db.iterate('rollback')
        assert await gen.next() is None


async def test_async_metadata():
    import gino
    db_ = await gino.Gino(PG_URL)
    assert isinstance((await db_.scalar('select now()')), datetime)
    await db_.pop_bind().close()
    assert db.bind is None


# noinspection PyUnreachableCode
async def test_acquire_timeout():
    import gino
    e = await gino.create_engine(PG_URL, min_size=1, max_size=1)
    async with e.acquire():
        with pytest.raises(asyncio.TimeoutError):
            async with e.acquire(timeout=0.1):
                assert False, 'Should not reach here'

    loop = asyncio.get_event_loop()
    f1 = loop.create_future()

    async def first():
        async with e.acquire() as conn:
            f1.set_result(None)
            await asyncio.sleep(0.2)
            # noinspection PyProtectedMember
            return conn.raw_connection._con

    async def second():
        async with e.acquire(lazy=True) as conn:
            conn = conn.execution_options(timeout=0.1)
            with pytest.raises(asyncio.TimeoutError):
                assert await conn.scalar('select 1')

    async def third():
        async with e.acquire(reuse=True, timeout=0.4) as conn:
            # noinspection PyProtectedMember
            return conn.raw_connection._con

    t1 = loop.create_task(first())
    await f1
    loop.create_task(second())
    t3 = loop.create_task(third())
    assert await t1 is await t3


# noinspection PyProtectedMember
async def test_lazy(mocker):
    import gino
    engine = await gino.create_engine(PG_URL, min_size=1, max_size=1)
    init_size = qsize(engine)
    async with engine.acquire(lazy=True):
        assert qsize(engine) == init_size
        assert len(engine._ctx.get()) == 1
    assert len(engine._ctx.get()) == 0
    assert qsize(engine) == init_size
    async with engine.acquire(lazy=True):
        assert qsize(engine) == init_size
        assert len(engine._ctx.get()) == 1
        assert await engine.scalar('select 1')
        assert qsize(engine) == init_size - 1
        assert len(engine._ctx.get()) == 1
    assert len(engine._ctx.get()) == 0
    assert qsize(engine) == init_size

    loop = asyncio.get_event_loop()
    fut = loop.create_future()

    async def block():
        async with engine.acquire():
            fut.set_result(None)
            await asyncio.sleep(0.3)

    blocker = loop.create_task(block())
    await fut
    init_size_2 = qsize(engine)
    ctx = engine.acquire(lazy=True)
    conn = await ctx.__aenter__()
    t1 = loop.create_task(
        conn.execution_options(timeout=0.1).scalar('select 1'))
    t2 = loop.create_task(ctx.__aexit__(None, None, None))
    with pytest.raises(asyncio.TimeoutError):
        await t1
    assert not await t2
    assert qsize(engine) == init_size_2
    await blocker
    assert qsize(engine) == init_size

    fut = loop.create_future()
    blocker = loop.create_task(block())
    await fut
    init_size_2 = qsize(engine)

    async def acquire_failed(*args, **kwargs):
        await asyncio.sleep(0.1)
        raise ValueError()

    mocker.patch('asyncpg.pool.Pool.acquire', new=acquire_failed)
    ctx = engine.acquire(lazy=True)
    conn = await ctx.__aenter__()
    t1 = loop.create_task(conn.scalar('select 1'))
    t2 = loop.create_task(conn.release(permanent=False))
    with pytest.raises(ValueError):
        await t1
    assert not await t2
    assert qsize(engine) == init_size_2

    await conn.release(permanent=False)
    assert qsize(engine) == init_size_2

    await blocker
    assert qsize(engine) == init_size


async def test_release(engine):
    init_size = qsize(engine)
    async with engine.acquire() as conn:
        assert await conn.scalar('select 8') == 8
        await conn.release(permanent=False)
        assert await conn.scalar('select 8') == 8
        await conn.release(permanent=False)
    with pytest.raises(ValueError, match='released permanently'):
        await conn.scalar('select 8')
    with pytest.raises(ValueError, match='already released'):
        await conn.release()

    conn = await engine.acquire()
    assert await conn.scalar('select 8') == 8
    await conn.release(permanent=False)
    assert await conn.scalar('select 8') == 8
    await conn.release()
    with pytest.raises(ValueError, match='released permanently'):
        await conn.scalar('select 8')

    conn1 = await engine.acquire()
    conn2 = await engine.acquire(reuse=True)
    conn3 = await engine.acquire()
    conn4 = await engine.acquire(reuse=True)
    assert await conn1.scalar('select 8') == 8
    assert await conn2.scalar('select 8') == 8
    assert await conn3.scalar('select 8') == 8
    assert await conn4.scalar('select 8') == 8

    await conn1.release(permanent=False)
    assert await conn2.scalar('select 8') == 8

    await conn2.release(permanent=False)
    assert await conn2.scalar('select 8') == 8

    await conn1.release()
    with pytest.raises(ValueError, match='released permanently'):
        await conn2.scalar('select 8')
    assert await conn4.scalar('select 8') == 8

    await conn4.release()
    with pytest.raises(ValueError, match='released permanently'):
        await conn4.scalar('select 8')

    assert await conn3.scalar('select 8') == 8
    await conn3.release(permanent=False)
    assert await conn3.scalar('select 8') == 8
    assert init_size - 1 == qsize(engine)
    await conn3.release(permanent=False)
    assert init_size == qsize(engine)
    await conn3.release()
    assert init_size == qsize(engine)

    conn1 = await engine.acquire()
    conn2 = await engine.acquire()
    conn3 = await engine.acquire()
    assert engine.current_connection is conn3
    await conn2.release()
    assert engine.current_connection is conn3
    await conn1.release()
    assert engine.current_connection is conn3
    await conn3.release()
    assert engine.current_connection is None
    assert init_size == qsize(engine)
