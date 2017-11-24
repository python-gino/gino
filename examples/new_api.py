import asyncio

import gino
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

metadata = sa.MetaData()
Model = gino.declarative_base(metadata)


class User(Model):
    __tablename__ = 'users'

    id = sa.Column(sa.BigInteger(), primary_key=True)
    nickname = sa.Column(sa.Unicode(), default='noname')
    profile = sa.Column(JSONB())

    def __repr__(self):
        return '{}<{}>'.format(self.nickname, self.id)


async def main():
    e = sa.create_engine('asyncpg://localhost/gino', strategy='gino')
    metadata.bind = e
    print(await e.execute('SELECT now()'))
    c = await e.connect()
    print(await c.execute('SELECT now()'))
    print(await User.query.execute())
    print(await User.query.execute().first())
    print(await User.query.scalar())
    async for user in User.query:
        print(user)


asyncio.get_event_loop().run_until_complete(main())
