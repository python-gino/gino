import getpass
import os
import random

import pytest
import sqlalchemy
from sqlalchemy.engine.url import URL

import gino
from gino.engine import AsyncEngine


@pytest.fixture(
    params=[db for db in ["postgresql", "mysql"] if not os.getenv(f"NO_{db.upper()}")]
)
def url(request):
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
    return rv


@pytest.fixture
async def engine(url):
    return await gino.create_engine(
        url, echo=os.getenv("DB_ECHO", "0").lower() in {"yes", "true", "1"}
    )


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

    async with engine.begin() as conn:
        await conn.execute(sqlalchemy.text("CREATE TABLE db_val (value integer)"))
        try:
            await conn.execute(add_db_val_sql.bindparams(value=value))
        except Exception:
            await conn.execute(sqlalchemy.text("DROP TABLE db_val"))
            raise

    yield value

    async with engine.begin() as conn:
        await conn.execute(sqlalchemy.text("DROP TABLE db_val"))
