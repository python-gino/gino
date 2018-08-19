import pytest
import gino
from gino.declarative import InvertDict
from asyncpg.exceptions import (
    UniqueViolationError, ForeignKeyViolationError, CheckViolationError)

from .models import User, UserSetting

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


async def test_inline_constraints_and_indexes(bind, engine):
    u = await User.create(nickname='test')
    us1 = await UserSetting.create(user_id=u.id, setting='skin', value='blue')

    # PrimaryKeyConstraint
    with pytest.raises(UniqueViolationError):
        await UserSetting.create(id=us1.id, user_id=u.id, setting='key1',
                                 value='val1')

    # ForeignKeyConstraint
    with pytest.raises(ForeignKeyViolationError):
        await UserSetting.create(user_id=42, setting='key2', value='val2')

    # UniqueConstraint
    with pytest.raises(UniqueViolationError):
        await UserSetting.create(user_id=u.id, setting='skin',
                                 value='duplicate-setting')

    # CheckConstraint
    with pytest.raises(CheckViolationError):
        await UserSetting.create(user_id=u.id, setting='key3', value='val3',
                                 col1=42)

    # Index
    status, result = await engine.status(
        "SELECT * FROM pg_indexes WHERE indexname = 'col2_idx'")
    assert status == 'SELECT 1'


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

        @db.declared_attr
        def unique_id(cls):
            return db.Column(db.Integer())

        @db.declared_attr
        def unique_constraint(cls):
            return db.UniqueConstraint('unique_id')

        @db.declared_attr
        def poly(cls):
            if cls.__name__ == 'Thing':
                return db.Column(db.Unicode())

        @db.declared_attr
        def __table_args__(cls):
            if cls.__name__ == 'Thing':
                return db.UniqueConstraint('poly'),

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

    assert Thing.unique_id is not Another.unique_id
    assert Thing.unique_id is Thing.__table__.c.unique_id
    c1, c2 = [list(filter(lambda c: list(c.columns)[0].name == 'unique_id',
                          m.__table__.constraints))[0]
              for m in [Thing, Another]]
    assert isinstance(c1, db.UniqueConstraint)
    assert isinstance(c2, db.UniqueConstraint)
    assert c1 is not c2

    assert isinstance(Thing.poly, db.Column)
    assert Another.poly is None
    for c in Thing.__table__.constraints:
        if list(c.columns)[0].name == 'poly':
            assert isinstance(c, db.UniqueConstraint)
            break
    else:
        assert False, 'Should not reach here'


# noinspection PyUnusedLocal
async def test_inherit_constraint():
    with pytest.raises(ValueError, match='already attached to another table'):
        class IllegalUserSetting(UserSetting):
            __table__ = None
            __tablename__ = 'bad_gino_user_settings'


async def test_abstract_model_error():
    class ConcreteModel(db.Model):
        __tablename__ = 'some_table'

        c = db.Column(db.Unicode())

    class AbstractModel(db.Model):
        pass

    with pytest.raises(TypeError, match='AbstractModel is abstract'):
        ConcreteModel.join(AbstractModel)

    with pytest.raises(TypeError, match='AbstractModel is abstract'):
        AbstractModel.join(ConcreteModel)

    with pytest.raises(TypeError, match='AbstractModel is abstract'):
        db.select(AbstractModel)

    with pytest.raises(TypeError, match='AbstractModel is abstract'):
        db.select([AbstractModel])

    with pytest.raises(TypeError, match='AbstractModel is abstract'):
        # noinspection PyStatementEffect
        AbstractModel.query

    with pytest.raises(TypeError, match='AbstractModel is abstract'):
        # noinspection PyStatementEffect
        AbstractModel.update

    am = AbstractModel()

    with pytest.raises(TypeError, match='AbstractModel is abstract'):
        await am.create()

    with pytest.raises(TypeError, match='AbstractModel is abstract'):
        await am.delete()

    req = am.update()

    with pytest.raises(TypeError, match='AbstractModel has no table'):
        await req.apply()

    with pytest.raises(TypeError, match='AbstractModel is abstract'):
        # noinspection PyStatementEffect
        AbstractModel.delete

    with pytest.raises(TypeError, match='AbstractModel is abstract'):
        AbstractModel.alias()

    with pytest.raises(TypeError, match='AbstractModel is abstract'):
        AbstractModel.alias()

    with pytest.raises(TypeError, match='AbstractModel is abstract'):
        await AbstractModel.get(1)


async def test_invert_dict():
    with pytest.raises(gino.GinoException,
                       match=r'Column name c1 already maps to \w+'):
        InvertDict({'col1': 'c1', 'col2': 'c1'})

    with pytest.raises(gino.GinoException,
                       match=r'Column name c1 already maps to \w+'):
        d = InvertDict()
        d['col1'] = 'c1'
        d['col2'] = 'c1'

    d = InvertDict()
    d['col1'] = 'c1'
    # it works for same key/value pair
    d['col1'] = 'c1'
    d['col2'] = 'c2'
    assert d.invert_get('c1') == 'col1'
    assert d.invert_get('c2') == 'col2'
