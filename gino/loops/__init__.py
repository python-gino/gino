from gino.loops.asyncio import AsyncioLoop
import sniffio


def get_loop():
    if sniffio.current_async_library() == 'trio':
        from .trio import TrioLoop
        return TrioLoop

    return AsyncioLoop
