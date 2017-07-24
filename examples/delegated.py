from gino import Gino
from sqlalchemy import select, Column, BigInteger, Unicode

db = Gino()


class User(db.Model):
    __tablename__ = 'users'

    id = Column(BigInteger(), primary_key=True)
    nickname = Column(Unicode(), default='noname')

    def __repr__(self):
        return '{}<{}>'.format(self.nickname, self.id)


async def main():
    async with db.create_pool('postgresql://localhost/gino') as pool:
        # You will need to create the database and table manually

        for u in await pool.fetch('SELECT * FROM users WHERE id > $1', 3):
            print(u)
        for u in await pool.fetch(User.query.where(User.id > 3)):
            print(u)
        for u in await pool.fetch(select([User.id])):
            print(u)
        u = await pool.fetchrow(User.query.where(User.id > 1))
        print(u)
        nickname = await pool.fetchval(
            User.select('nickname').where(User.id == 1))
        print(nickname)
        status = await pool.execute(User.query)
        print(status)
        async with pool.acquire() as conn:
            async with conn.transaction():
                async for u in conn.cursor(User.query.where(User.id > 3)):
                    print(u)


if __name__ == '__main__':
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
