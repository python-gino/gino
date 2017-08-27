from gino import Gino, enable_task_local

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

        q = User.query
        print(await q.gino.first())
        pool.execution_options['return_model'] = False
        print(await q.gino.first())
        async with db.acquire() as conn:
            conn.execution_options['return_model'] = True
            print(await q.gino.first())
            print(await q.execution_options(return_model=False).gino.first())
        print(await q.execution_options(return_model=True).gino.first())
        print(await q.gino.first())
        pool.execution_options.clear()
        print(await q.gino.first())


if __name__ == '__main__':
    import asyncio

    loop = asyncio.get_event_loop()
    enable_task_local(loop)
    loop.run_until_complete(main())
