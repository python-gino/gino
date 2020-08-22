import getpass
import os
import random
from inspect import iscoroutinefunction

import pytest
import sqlalchemy
from sqlalchemy.engine.url import URL

import gino
from gino.engine import AsyncEngine

USE_TRIO = os.environ.get("USE_TRIO", "0").lower() in {"1", "yes", "true", "y"}


def pytest_addhooks(pluginmanager):
    if USE_TRIO:
        pluginmanager.unregister(name="asyncio")
    else:
        pluginmanager.unregister(name="trio")
        pluginmanager.unregister(name="anyio")


def pytest_collection_modifyitems(items):
    for item in items:
        if hasattr(item.obj, "hypothesis"):
            test_func = item.obj.hypothesis.inner_test
        else:
            test_func = item.obj
        if iscoroutinefunction(test_func):
            if USE_TRIO:
                item.add_marker(pytest.mark.trio)
            else:
                item.add_marker(pytest.mark.asyncio)


@pytest.fixture
def use_trio():
    return USE_TRIO


@pytest.fixture(
    params=[db for db in ["postgresql", "mysql"] if not os.getenv(f"NO_{db.upper()}")]
)
async def url(request):
    driver = request.param
    rv = URL(
        drivername=driver,
        **{
            key: os.getenv(f"{driver.upper()}_{key.upper()}")
            for key in ("username", "password", "host", "port", "database", "query")
        },
    )
    if driver == "mysql":
        if rv.username is None:
            rv.username = getpass.getuser()
        if rv.database is None:
            rv.database = rv.username
    if USE_TRIO and request.param == "postgresql":
        import trio_asyncio

        async with trio_asyncio.open_loop() as loop:
            try:
                yield rv
            finally:
                await loop.stop().wait()
    else:
        yield rv


@pytest.fixture
async def engine(url):
    async with gino.create_engine(
        url, echo=os.getenv("DB_ECHO", "0").lower() in {"yes", "true", "1"}
    ) as engine:
        yield engine


@pytest.fixture
async def conn(engine: AsyncEngine):
    async with engine.connect() as conn:
        yield conn


@pytest.fixture(params=["SSCursor", "BufferedCursor"])
async def con(conn, request):
    if request.param == "SSCursor":
        async with conn.execution_options(stream_results=True).begin():
            yield conn
    else:
        yield conn


@pytest.fixture
async def tx_conn(engine: AsyncEngine):
    async with engine.begin() as conn:
        yield conn


@pytest.fixture
def get_db_val_sql():
    return sqlalchemy.text("SELECT * FROM db_val ORDER BY value")


@pytest.fixture
def set_db_val_sql():
    return sqlalchemy.text("UPDATE db_val SET value = :value")


@pytest.fixture
def incr_db_val_sql():
    return sqlalchemy.text("UPDATE db_val SET value = value + 1")


@pytest.fixture
def find_db_val_sql():
    return sqlalchemy.text("SELECT * FROM db_val WHERE value = :value")


@pytest.fixture
def add_db_val_sql():
    return sqlalchemy.text("INSERT INTO db_val VALUES (:value)")


@pytest.fixture
async def db_val(add_db_val_sql, engine: AsyncEngine):
    value = random.randint(1024, 65536)

    try:
        await engine.execute(sqlalchemy.text("CREATE TABLE db_val (value integer)"))
        await engine.execute(add_db_val_sql.bindparams(value=value))
    except Exception:
        await engine.execute(sqlalchemy.text("DROP TABLE db_val"))
        raise

    yield value

    await engine.execute(sqlalchemy.text("DROP TABLE db_val"))
