# Waiting for https://www.python.org/dev/peps/pep-0550/

import asyncio

_original_task_factories = {}


def get_local():
    """Get local storage from current task.

    Returns a dict if task local is enabled for current loop, or ``None``
    otherwise. Please note, if you create a new task from an existing task,
    the new task will by default inherit the same local storage object from
    the existing task. Use ``is_local_root` to check the inherit state, and use
    ``reset_local`` to spawn tasks without inheriting. See the two functions
    for more information.
    """
    return getattr(asyncio.Task.current_task(), 'task_local', None)


def task_factory(loop, coro):
    loop.set_task_factory(_original_task_factories.get(loop))
    try:
        task = loop.create_task(coro)
        if getattr(task, '_source_traceback', None):
            del getattr(task, '_source_traceback')[-2:]

        local = get_local()
        task.task_local = {} if local is None else local
        task.task_local_is_root = local is None

        return task
    finally:
        loop.set_task_factory(task_factory)


def reset_local(coro_or_future=None, *, loop=None):
    """Reset local to empty dict within given routine, or current if not given.

    Please note, this works only if the local was inherited from another
    routine, or this is a no-op. That means, calling ``reset_local`` a second
    time on the same routine won't set its local to empty dict, because its
    local was already non-inherited after the first call.

    This method always return a future object. New task will be created and
    returned if the parameter is a coroutine or awaitable object. Therefore it
    is practical to use this method to spawn detached tasks.
    """
    if coro_or_future is None:
        coro_or_future = asyncio.Task.current_task()

    if asyncio.isfuture(coro_or_future):
        if is_local_root(coro_or_future) is False:
            coro_or_future.task_local = {}
            coro_or_future.task_local_is_root = True
        return coro_or_future
    else:
        return reset_local(asyncio.ensure_future(coro_or_future, loop=loop))


def is_local_root(task=None):
    """Check if local of the given task is inherited or not.

    If task is not given, current task is used. Returns ``None`` if the task
    has no local, or ``True``/``False`` for the inherit state.
    """
    if task is None:
        task = asyncio.Task.current_task()
    return getattr(task, 'task_local_is_root', None)


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
