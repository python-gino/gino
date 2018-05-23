import pytest
from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey
from sqlalchemy.engine.result import RowProxy

from .models import PG_URL

pytestmark = pytest.mark.asyncio


async def test_engine_only():
    import gino
    from gino.schema import GinoSchemaVisitor

    metadata = MetaData()

    users = Table(
        'users', metadata,
        Column('id', Integer, primary_key=True),
        Column('name', String),
        Column('fullname', String),
    )

    Table(
        'addresses', metadata,
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
        assert isinstance(res[0], RowProxy)
    finally:
        await GinoSchemaVisitor(metadata).drop_all(engine)


async def test_core():
    from gino import Gino

    db = Gino()

    users = db.Table(
        'users', db,
        db.Column('id', db.Integer, primary_key=True),
        db.Column('name', db.String),
        db.Column('fullname', db.String),
    )

    db.Table(
        'addresses', db,
        db.Column('id', db.Integer, primary_key=True),
        db.Column('user_id', None, db.ForeignKey('users.id')),
        db.Column('email_address', db.String, nullable=False)
    )

    async with db.with_bind(PG_URL):
        await db.gino.create_all()
        try:
            await users.insert().values(
                name='jack',
                fullname='Jack Jones',
            ).gino.status()
            res = await users.select().gino.all()
            assert isinstance(res[0], RowProxy)
        finally:
            await db.gino.drop_all()


async def test_orm():
    from gino import Gino

    db = Gino()

    class User(db.Model):
        __tablename__ = 'users'

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String)
        fullname = db.Column(db.String)

    class Address(db.Model):
        __tablename__ = 'addresses'

        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(None, db.ForeignKey('users.id'))
        email_address = db.Column(db.String, nullable=False)

    async with db.with_bind(PG_URL):
        await db.gino.create_all()
        try:
            await User.create(name='jack', fullname='Jack Jones')
            res = await User.query.gino.all()
            assert isinstance(res[0], User)
        finally:
            await db.gino.drop_all()
