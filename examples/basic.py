import asyncpg
from gino import Gino
from sqlalchemy import Column, BigInteger, Unicode

db = Gino()


class User(db.Model):
    __tablename__ = 'users'

    id = Column(BigInteger(), primary_key=True)
    nickname = Column(Unicode(), default='noname')

    def __repr__(self):
        return '{}<{}>'.format(self.nickname, self.id)


async def main():
    conn = await asyncpg.connect('postgresql://localhost/gino')

    # You will need to create the database and table manually

    print(await User.create(bind=conn, nickname='fantix'))
    print(await User.get(1, bind=conn))
    async with conn.transaction():
        query, params = db.compile(User.query.where(User.id > 3))
        async for u in User.map(conn.cursor(query, *params)):
            print(u)


if __name__ == '__main__':
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
