import asyncio
from gino import Gino


db = Gino()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.BigInteger(), primary_key=True)
    nickname = db.Column(db.Unicode(), default='noname')
    profile = db.Column(db.JSONB())

    def __repr__(self):
        return '{}<{}>'.format(self.nickname, self.id)


async def main():
    e = await db.create_engine('postgresql://localhost/gino', min_size=0)
    print(await e.execute('SELECT now()'))
    c = await e.connect()
    print(await c.execute('SELECT now()'))
    print(await User.query.execute())
    print(await User.query.execute().first())
    print(await User.query.scalar())
    async for user in User.query:
        print(user)


asyncio.get_event_loop().run_until_complete(main())
