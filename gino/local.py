# Waiting for https://www.python.org/dev/peps/pep-0550/

import asyncio

_original_task_factories = {}


def get_local():
    return getattr(asyncio.Task.current_task(), 'task_local', None)


def task_factory(loop, coro):
    orig = _original_task_factories.get(loop)
    loop.set_task_factory(orig)
    task = loop.create_task(coro)
    loop.set_task_factory(task_factory)

    if getattr(task, '_source_traceback', None):
        del getattr(task, '_source_traceback')[-2:]

    task.task_local = get_local() or {}

    return task


def enable_task_local(loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()
    if loop in _original_task_factories:
        return
    _original_task_factories[loop] = loop.get_task_factory()
    loop.set_task_factory(task_factory)


def disable_task_local(loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()
    if loop in _original_task_factories:
        loop.set_task_factory(_original_task_factories.pop(loop))
