import os

import pytest
from sqlalchemy.engine.url import URL

import gino


@pytest.fixture(params=["postgresql", "mysql"])
def url(request):
    driver = request.param
    return URL(
        drivername=driver,
        **{
            key: os.getenv(f"{driver.upper()}_{key.upper()}")
            for key in ("username", "password", "host", "port", "database", "query")
        },
    )


@pytest.fixture
def engine(url):
    return gino.create_engine(
        url, echo=os.getenv("DB_ECHO", "0").lower() in {"yes", "true", "1"}
    )
