import asyncio


class AsyncioLoop:
    @staticmethod
    async def wait_for_with_timeout(fn, timeout):
        return await asyncio.wait_for(fn(), timeout=timeout)

    Lock = asyncio.Lock
