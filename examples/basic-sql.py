import os
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine.url import URL

import gino

# url can also be a string like "postgresql://username:password@localhost:5432/database"
from gino.engine import AsyncConnection

url = os.getenv("DB_URL")
if url is None:
    driver = os.getenv("DB_DRIVER", "postgresql")
    url = URL(
        drivername=driver,
        **{
            key: os.getenv(f"{driver.upper()}_{key.upper()}")
            for key in ("username", "password", "host", "port", "database", "query")
        },
    )


async def engine_and_connection():
    # you may use either async context:
    async with gino.create_engine(url) as engine:
        async with engine.connect() as conn:
            assert await conn.execute(text("SELECT 123")).scalar() == 123

    # or manual await:
    engine = await gino.create_engine(url)
    conn = await engine.connect()
    assert await conn.execute(text("SELECT 123")).scalar() == 123
    await conn.close()
    await engine.close()


async def execute_and_result():
    async with gino.create_engine(url) as engine:
        async with engine.connect() as conn:
            await _execute_and_result(conn)


async def _execute_and_result(conn: AsyncConnection):
    print("Directly execute a SQL, discarding results")
    await conn.execute(
        text("CREATE TABLE sql_users (id INTEGER PRIMARY KEY, name TEXT)")
    )

    print("Use executemany() to insert multiple values")
    await conn.execute(
        text("INSERT INTO sql_users (id, name) VALUES (:id, :name)"),
        [
            dict(id=1, name="Alice"),
            dict(id=2, name="Bob"),
            dict(id=3, name="Charlie"),
            dict(id=4, name="Dave"),
        ],
    )

    SELECT_ALL = text("SELECT * FROM sql_users")

    print("Fetch all results in one go:")
    rows = await conn.execute(SELECT_ALL).all()
    for row in rows:
        print(row["id"], row["name"])

    print("Or fetch them separately with a server-side cursor:")
    rows = []
    async with conn.begin():
        async with conn.execute(
            SELECT_ALL, execution_options=dict(stream_results=True)
        ) as result:
            rows.append(await result.fetchone())
            rows.extend(await result.fetchmany(2))
            rows.extend(await result.fetchall())
    for row in rows:
        print(row["id"], row["name"])

    print("Or use an async iterator:")
    async with conn.begin():
        async for row in conn.execute(
            SELECT_ALL, execution_options=dict(stream_results=True)
        ).yield_per(2):
            print(row["id"], row["name"])

    print("Return one and only one row (raise errors otherwise):")
    row = await conn.execute(text("SELECT * FROM sql_users LIMIT 1")).one()
    print(row["id"], row["name"])

    print("Return one row or None (raise errors if multiple found):")
    row = await conn.execute(
        text("SELECT * FROM sql_users WHERE id = :id"), {"id": 2}
    ).one_or_none()
    if row is not None:
        print(row["id"], row["name"])

    print("Return only the first row or None:")
    row = await conn.execute(SELECT_ALL).first()
    if row is not None:
        print(row["id"], row["name"])

    print("Select a single value:")
    now: datetime = await conn.execute(text("SELECT now()")).scalar()
    print(now.strftime("%Y-%m-%d %H:%M:%S"))
