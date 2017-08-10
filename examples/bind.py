import asyncpg
from gino import Gino

db = Gino()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.BigInteger(), primary_key=True)
    nickname = db.Column(db.Unicode(), default='noname')

    def __repr__(self):
        return '{}<{}>'.format(self.nickname, self.id)


async def main():
    conn = await asyncpg.connect('postgresql://localhost/gino')
    db.bind = conn

    # You will need to create the database and table manually

    u = await User.create(nickname='fantix')
    print(u)
    u = await User.get(u.id)
    print(u)
    await u.update(nickname='daisy')
    print(u)
    print(await u.delete())


if __name__ == '__main__':
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
