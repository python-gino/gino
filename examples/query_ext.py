from gino import Gino, enable_task_local

db = Gino()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.BigInteger(), primary_key=True)
    nickname = db.Column(db.Unicode(), default='noname')

    def __repr__(self):
        return '{}<{}>'.format(self.nickname, self.id)


async def main():
    await db.create_pool('postgresql://localhost/gino')
    print(await User.query.gino.first())
    async with db.acquire():
        async with db.acquire(lazy=True):
            print(await User.query.gino.first())
            print(await User.query.gino.first())
        print(await User.query.gino.first())
    async with db.acquire(lazy=True):
        async with db.acquire():
            print(await User.query.gino.first())
    async with db.acquire(lazy=True):
        async with db.acquire(lazy=True):
            print(await User.query.gino.first())
    async with db.acquire(lazy=True):
        async with db.transaction():
            async with db.transaction():
                async for u in User.query.gino.iterate():
                    print(u)
                    break
                print(await User.query.gino.first())
    async with db.acquire():
        async with db.acquire(reuse=False):
            print(await User.query.gino.first())


if __name__ == '__main__':
    import asyncio

    loop = asyncio.get_event_loop()
    enable_task_local(loop)
    loop.run_until_complete(main())
