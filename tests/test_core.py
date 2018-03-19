import pytest
from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey

from .models import PG_URL

pytestmark = pytest.mark.asyncio


async def test_engine_only():
    import gino
    from gino.schema import GinoSchemaVisitor

    metadata = MetaData()

    users = Table('users', metadata,
                  Column('id', Integer, primary_key=True),
                  Column('name', String),
                  Column('fullname', String),
                  )

    addresses = Table('addresses', metadata,
                      Column('id', Integer, primary_key=True),
                      Column('user_id', None, ForeignKey('users.id')),
                      Column('email_address', String, nullable=False)
                      )

    engine = await gino.create_engine(PG_URL)
    await GinoSchemaVisitor(metadata).create_all(engine)
    try:
        ins = users.insert().values(name='jack', fullname='Jack Jones')
        await engine.status(ins)
        res = await engine.all(users.select())
        print(res)
        print(type(res))
        print(type(res[0]))
    finally:
        await GinoSchemaVisitor(metadata).drop_all(engine)
