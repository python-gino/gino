import sqlalchemy as sa
from gino import Gino

db = Gino()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.BigInteger(), primary_key=True)
    user = db.Column(db.Unicode())
    age = db.Column(db.BigInteger())
    message = db.Column(db.Unicode())

db_endpoint = 'postgres://postgres@localhost/mydb'
db_engine = sa.create_engine(db_endpoint)
db.create_all(bind=db_engine)
db_engine.dispose()
