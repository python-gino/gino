import pytest

import gino

from .models import User

pytestmark = pytest.mark.asyncio
db = gino.Gino()


# noinspection PyUnusedLocal
async def test_column_not_deletable(bind):
    u = await User.create(nickname='test')
    with pytest.raises(AttributeError):
        del u.nickname


async def test_table_args():
    class Model(db.Model):
        __tablename__ = 'model1'

    assert Model.__table__.implicit_returning

    class Model(db.Model):
        __tablename__ = 'model2'

        __table_args__ = dict(implicit_returning=False)

    assert not Model.__table__.implicit_returning

    class Model(db.Model):
        __tablename__ = 'model3'

        __table_args__ = db.Column('new_col'), dict(implicit_returning=False)

    assert not Model.__table__.implicit_returning
    assert not hasattr(Model, 'new_col')
    assert not hasattr(Model.__table__.c, 'nonexist')
    assert hasattr(Model.__table__.c, 'new_col')

    class Model(db.Model):
        __tablename__ = 'model4'
        __table_args__ = db.Column('col1'), db.Column('col2')

        col3 = db.Column()

    assert not hasattr(Model, 'col1')
    assert not hasattr(Model, 'col2')
    assert hasattr(Model, 'col3')
    assert hasattr(Model.__table__.c, 'col1')
    assert hasattr(Model.__table__.c, 'col2')
    assert hasattr(Model.__table__.c, 'col3')


async def test_join_t112(engine):
    class Car(db.Model):
        __tablename__ = 'cars'

        id = db.Column(db.BigInteger(), primary_key=True)

    class Wheel(db.Model):
        __tablename__ = 'wheels'

        id = db.Column(db.BigInteger(), primary_key=True)
        car_id = db.Column(db.ForeignKey('cars.id'))

    sql = ('SELECT wheels.id, wheels.car_id, cars.id \nFROM wheels '
           'JOIN cars ON cars.id = wheels.car_id')

    assert engine.compile(Wheel.join(Car).select())[0] == sql


async def test_mixin():
    class Tracked:
        created = db.Column(db.DateTime(timezone=True))

    class Audit(Tracked):
        pass

    class Thing(Audit, db.Model):
        __tablename__ = 'thing'

        id = db.Column(db.Integer, primary_key=True)

    class Another(Audit, db.Model):
        __tablename__ = 'another'

        id = db.Column(db.Integer, primary_key=True)

    assert isinstance(Thing.__table__.c.created, db.Column)
    assert isinstance(Another.__table__.c.created, db.Column)
    assert Thing.created is not Another.created
    assert Thing.created is Thing.__table__.c.created
    assert Another.created is Another.__table__.c.created
