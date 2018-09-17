import trio


class TrioLoop:
    @staticmethod
    async def wait_for_with_timeout(fn, timeout):
        with trio.fail_after(timeout):
            return await fn() 

    Lock = trio.Lock