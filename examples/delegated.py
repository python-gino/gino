from gino import Gino

db = Gino()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.BigInteger(), primary_key=True)
    nickname = db.Column(db.Unicode(), default='noname')

    def __repr__(self):
        return '{}<{}>'.format(self.nickname, self.id)


async def main():
    async with db.create_pool('postgresql://localhost/gino') as pool:
        # You will need to create the database and table manually

        for u in await pool.all(User.query.where(User.id > 3)):
            print(u)
        for u in await pool.all(db.select([User.id])):
            print(u)
        u = await pool.first(User.query.where(User.id > 1))
        print(u)
        nickname = await pool.scalar(
            User.select('nickname').where(User.id == 1))
        print(nickname)
        async with pool.acquire() as conn:
            async with conn.transaction():
                async for u in conn.iterate(User.query.where(User.id > 3)):
                    print(u)
    await db.create_pool('postgresql://localhost/gino')
    async with db.transaction() as (conn, tx):
        async for u in conn.iterate(User.query.where(User.id > 3)):
            print(u)


if __name__ == '__main__':
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
