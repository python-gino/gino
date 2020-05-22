from functools import partial

import anyio
import pytest
from sqlalchemy import exc, text
from sqlalchemy.engine.url import URL

import gino
from gino.engine import AsyncEngine, AsyncConnection
from gino.pool.base import NullPool


async def take_conn(tg: anyio.TaskGroup, engine: AsyncEngine):
    ready = anyio.create_queue(0)
    close = anyio.create_event()

    async def run():
        while True:
            try:
                async with engine.connect():
                    await ready.put(None)
                    async with anyio.fail_after(10):
                        await close.wait()
                    return
            except exc.TimeoutError as e:
                await ready.put(e)
            except Exception as e:
                await ready.put(e)
                return

    await tg.spawn(run)
    return ready, close


@pytest.fixture
async def connect(url):
    async with anyio.create_task_group() as tg:
        async with gino.create_engine(
            url, pool_size=2, max_overflow=1, pool_timeout=1
        ) as engine:
            assert engine.pool.timeout() == 1
            async with anyio.fail_after(10):
                yield partial(take_conn, tg, engine)


async def test_overflow(connect):
    ready1, close1 = await connect()
    ready2, close2 = await connect()
    ready3, close3 = await connect()
    assert await ready1.get() is None
    assert await ready2.get() is None
    assert await ready3.get() is None

    ready4, close4 = await connect()
    async with anyio.fail_after(1.5):
        assert isinstance(await ready4.get(), exc.TimeoutError)
    async with anyio.move_on_after(0.5):
        assert await ready4.get() is not None
    assert ready4.empty()

    await close1.set()
    assert await ready4.get() is None
    await close2.set()
    await close3.set()
    await close4.set()


async def test_connect_during_close(connect):
    ready1, close1 = await connect()
    assert await ready1.get() is None

    async def run():
        await anyio.sleep(1)  # wait until pool is closing
        ready2, close2 = await connect()
        assert isinstance(await ready2.get(), exc.InvalidRequestError)
        await close1.set()

    await connect.args[0].spawn(run)


async def test_connect_fail(url: URL, engine: AsyncEngine, monkeypatch, mocker):
    monkeypatch.setattr(url, "database", "nonexist")
    with pytest.raises((exc.OperationalError, exc.DBAPIError)) as e:
        await gino.create_engine(url)

    assert engine.pool.checkedin() == 1
    async with engine.connect():
        assert engine.pool.checkedin() == 0
        monkeypatch.setattr(
            engine.pool, "_creator", mocker.Mock(side_effect=e.value.orig)
        )
        with pytest.raises((exc.OperationalError, exc.DBAPIError)):
            async with engine.connect():
                pass
        assert engine.pool.checkedin() == 0


async def test_reset(engine: AsyncEngine, conn, monkeypatch, mocker):
    assert engine.pool.overflow() + engine.pool.size() == 1
    assert engine.pool.checkedin() == 0

    with pytest.raises(exc.DBAPIError) as e:
        await conn.execute(text("SELECT * FROM non_exist"))

    assert engine.pool.overflow() + engine.pool.size() == 1
    assert engine.pool.checkedin() == 0

    monkeypatch.setattr(engine.pool, "_reset", mocker.Mock(side_effect=e.value.orig))
    async with engine.connect():
        assert engine.pool.overflow() + engine.pool.size() == 2
        assert engine.pool.checkedin() == 0

    assert engine.pool.overflow() + engine.pool.size() == 1
    assert engine.pool.checkedin() == 0


async def test_infinite_overflow(url: URL):
    async with gino.create_engine(url, pool_size=2, max_overflow=-1) as engine:
        assert engine.pool.overflow() + engine.pool.size() == 1
        assert engine.pool.checkedin() == 1

        try:
            conns = []
            for i in range(32):
                conns.append(await engine.connect())
                assert engine.pool.overflow() + engine.pool.size() == i + 1
                assert engine.pool.checkedin() == 0
        finally:
            size = len(conns)
            while conns:
                try:
                    await conns.pop().close()
                    assert engine.pool.overflow() + engine.pool.size() == len(conns)
                    assert engine.pool.checkedin() == min(size - len(conns), 2)
                except Exception:
                    pass
    assert engine.pool.overflow() + engine.pool.size() == 0
    assert engine.pool.checkedin() == 0


async def close_pool(conns):
    async with anyio.create_task_group() as tg:
        for conn in conns:
            await tg.spawn(conn.close)


async def test_different(url: URL):
    async with gino.create_engine(url, pool_size=3, max_overflow=3) as engine:
        conns = []
        raw_conns = set()
        try:
            for i in range(6):
                conn = await engine.connect()
                conns.append(conn)
                raw_conns.add(conn.raw_connection)
            assert len(conns) == len(raw_conns)
        finally:
            await close_pool(conns)


@pytest.mark.parametrize("use_lifo", [True, False])
async def test_lifo_fifo(url: URL, use_lifo):
    async with gino.create_engine(
        url, pool_size=5, max_overflow=1, pool_use_lifo=use_lifo
    ) as engine:
        stack = []
        conns = []
        try:
            for i in range(6):
                conn = await engine.connect()
                conns.append(conn)
            while conns:
                conn = conns.pop()
                stack.append(conn.raw_connection)
                await conn.close()
            for i in range(6):
                conn: AsyncConnection = await engine.connect()
                conns.append(conn)
                if i < 5:
                    expected = stack[-2 - i] if use_lifo else stack[i]
                    assert conn.raw_connection is expected
                else:
                    assert conn.raw_connection is not stack[-1]
        finally:
            await close_pool(conns)


async def test_null_pool(url: URL):
    conns = []
    try:
        async with gino.create_engine(url, poolclass=NullPool) as engine:
            assert isinstance(engine.pool, NullPool)
            for i in range(32):
                conns.append(await engine.connect())
    finally:
        await close_pool(conns)
