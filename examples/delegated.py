from gino import Gino, create_engine

db = Gino()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.BigInteger(), primary_key=True)
    nickname = db.Column(db.Unicode(), default='noname')

    def __repr__(self):
        return '{}<{}>'.format(self.nickname, self.id)


async def main():
    e = await create_engine('postgresql://localhost/gino')
    # You will need to create the database and table manually

    for u in await e.all(User.query.where(User.id > 3)):
        print(u)
    for u in await e.all(db.select([User.id])):
        print(u)
    u = await e.first(User.query.where(User.id > 1))
    print(u)
    nickname = await e.scalar(
        User.select('nickname').where(User.id == 1))
    print(nickname)
    async with e.acquire() as conn:
        async with conn.transaction():
            async for u in conn.iterate(User.query.where(User.id > 3)):
                print(u)
    async with e.transaction() as tx:
        async for u in tx.connection.iterate(User.query.where(User.id > 3)):
            print(u)


if __name__ == '__main__':
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
