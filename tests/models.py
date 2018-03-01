import os
import enum
from datetime import datetime

from gino import Gino
from gino.dialects.asyncpg import JSONB

DB_ARGS = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    port=os.getenv('DB_PORT', 5432),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASS', ''),
    database=os.getenv('DB_NAME', 'postgres'),
)
PG_URL = 'postgresql://{user}:{password}@{host}:{port}/{database}'.format(
    **DB_ARGS)
db = Gino()


class UserType(enum.Enum):
    USER = 'USER'


class User(db.Model):
    __tablename__ = 'gino_users'

    id = db.Column(db.BigInteger(), primary_key=True)
    nickname = db.Column(db.Unicode(), default='noname')
    profile = db.Column(JSONB(), nullable=False, server_default='{}')
    type = db.Column(
        db.Enum(UserType),
        nullable=False,
        default=UserType.USER,
    )
    name = db.StringProperty()
    age = db.IntegerProperty(default=18)
    balance = db.IntegerProperty(default=0)
    birthday = db.DateTimeProperty(
        default=lambda i: datetime.utcfromtimestamp(0))

    @balance.after_get
    def balance(self, val):
        if val is None:
            return 0.0
        return float(val)

    def __repr__(self):
        return '{}<{}>'.format(self.nickname, self.id)


class Friendship(db.Model):
    __tablename__ = 'gino_friendship'

    my_id = db.Column(db.BigInteger(), primary_key=True)
    friend_id = db.Column(db.BigInteger(), primary_key=True)

    def __repr__(self):
        return 'Friends<{}, {}>'.format(self.my_id, self.friend_id)


def qsize(engine):
    # noinspection PyProtectedMember
    return engine.raw_pool._queue.qsize()
