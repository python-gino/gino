import getpass
import os
import random

import pytest
import sqlalchemy
from sqlalchemy.engine.url import URL

import gino


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
def engine(url):
    return gino.create_engine(
        url, echo=os.getenv("DB_ECHO", "0").lower() in {"yes", "true", "1"}
    )


@pytest.fixture
def get_db_val_sql():
    return sqlalchemy.text("SELECT * FROM db_val")


@pytest.fixture
def set_db_val_sql():
    return sqlalchemy.text("UPDATE db_val SET value = :value")


@pytest.fixture
async def db_val(engine):
    value = random.randint(0, 65536)

    async with engine.begin() as conn:
        await conn.execute(sqlalchemy.text("CREATE TABLE db_val (value integer)"))
        try:
            await conn.execute(
                sqlalchemy.text("INSERT INTO db_val VALUES (:value)").bindparams(
                    value=value
                )
            )
        except Exception:
            await conn.execute(sqlalchemy.text("DROP TABLE db_val"))
            raise

    yield value

    async with engine.begin() as conn:
        await conn.execute(sqlalchemy.text("DROP TABLE db_val"))
