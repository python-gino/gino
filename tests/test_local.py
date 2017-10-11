import asyncio

import pytest
from gino import get_local, reset_local, is_local_root

pytestmark = pytest.mark.asyncio


async def sub(result):
    result.append(get_local().get('val'))


# noinspection PyUnusedLocal
async def test_attached(task_local):
    get_local()['val'] = 123
    result = []
    await asyncio.ensure_future(sub(result))
    assert result[0] == 123


# noinspection PyUnusedLocal
async def test_detached(task_local):
    get_local()['val'] = 123
    result = []
    await reset_local(sub(result))
    assert result[0] is None


async def test_reset_disabled():
    result = []
    fut = reset_local(sub(result))
    with pytest.raises(AttributeError):
        await fut
    assert len(result) == 0


async def sub_set():
    get_local()['val'] = 123


# noinspection PyUnusedLocal
async def test_attached_reverse(task_local):
    await asyncio.ensure_future(sub_set())
    assert get_local().get('val') == 123


# noinspection PyUnusedLocal
async def test_detached_reverse(task_local):
    await reset_local(sub_set())
    assert get_local().get('val') is None


# noinspection PyUnusedLocal
async def test_accept_task(task_local):
    await reset_local(asyncio.ensure_future(sub_set()))
    assert get_local().get('val') is None


async def grand_sub():
    assert not is_local_root()
    assert get_local().get('val') == 456


async def sub_reset():
    assert is_local_root() is False
    assert get_local().get('val') == 123

    reset_local()
    assert is_local_root()
    assert get_local().get('val') is None

    get_local()['val'] = 456
    assert get_local().get('val') == 456
    await asyncio.ensure_future(grand_sub())

    reset_local()
    assert get_local().get('val') == 456
    await asyncio.ensure_future(grand_sub())


# noinspection PyUnusedLocal
async def test_inline_reset(task_local):
    get_local()['val'] = 123
    await asyncio.ensure_future(sub_reset())
    get_local()['val'] = 123
