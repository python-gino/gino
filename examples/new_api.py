import asyncio
import gino

metadata = gino.MetaData()
Model = gino.declarative_base(metadata)


class User(Model):
    __tablename__ = 'users'

    id = gino.Column(gino.BigInteger(), primary_key=True)
    nickname = gino.Column(gino.Unicode(), default='noname')
    profile = gino.Column(gino.JSONB())

    def __repr__(self):
        return '{}<{}>'.format(self.nickname, self.id)


async def main():
    e = gino.create_engine('postgresql+asyncpg://localhost/gino',
                           min_size=0, strategy='gino')
    metadata.bind = e
    # e = db.create_engine('asyncpg://localhost/gino')
    print(await e.execute('SELECT now()'))
    c = await e.connect()
    print(await c.execute('SELECT now()'))
    print(await User.query.execute())
    print(await User.query.execute().first())
    print(await User.query.scalar())
    async for user in User.query:
        print(user)


asyncio.get_event_loop().run_until_complete(main())
