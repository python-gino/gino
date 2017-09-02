from gino import Gino, enable_task_local

db = Gino()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.BigInteger(), primary_key=True)
    nickname = db.Column(db.Unicode(), default='noname')
    profile = db.Column(db.JSONB())

    def __repr__(self):
        return '{}<{}> {}'.format(self.nickname, self.id, self.profile)


async def main():
    async with db.create_pool('postgresql://localhost/gino') as pool:
        # You will need to create the database and table manually

        print(await User.query.gino.first())
        pool.execution_options['return_model'] = False
        print(await User.query.gino.first())
        async with db.acquire() as conn:
            conn.execution_options['return_model'] = True
            print(await User.query.gino.first())
            print(await User.query.execution_options(
                return_model=False).gino.first())
        print(await User.query.execution_options(
            return_model=True).gino.first())
        print(await User.query.gino.first())
        pool.execution_options.clear()
        print(await User.query.gino.first())


if __name__ == '__main__':
    import asyncio

    loop = asyncio.get_event_loop()
    enable_task_local(loop)
    loop.run_until_complete(main())
