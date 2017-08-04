import os

from gino import Gino
from sqlalchemy import Column, BigInteger, Unicode

DB_ARGS = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    port=os.getenv('DB_PORT', 5432),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASS', ''),
    database=os.getenv('DB_NAME', 'postgres'),
)
db = Gino()


class User(db.Model):
    __tablename__ = 'gino_users'

    id = Column(BigInteger(), primary_key=True)
    nickname = Column(Unicode(), default='noname')

    def __repr__(self):
        return '{}<{}>'.format(self.nickname, self.id)


class Friendship(db.Model):
    __tablename__ = 'gino_friendship'

    my_id = Column(BigInteger(), primary_key=True)
    friend_id = Column(BigInteger(), primary_key=True)

    def __repr__(self):
        return 'Friends<{}, {}>'.format(self.my_id, self.friend_id)
