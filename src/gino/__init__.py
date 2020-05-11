def create_engine(url, **kwargs):
    from copy import copy
    from sqlalchemy.engine import create_engine
    from sqlalchemy.engine.url import make_url
    from .engine import AsyncEngine

    url = make_url(url)
    if url.drivername in {"postgresql", "postgres"}:
        url = copy(url)
        url.drivername = "postgresql+asyncpg"
    if url.drivername in {"mysql"}:
        url = copy(url)
        url.drivername = "mysql+aiomysql"

    kwargs["_future_engine_class"] = AsyncEngine
    return create_engine(url, **kwargs)
