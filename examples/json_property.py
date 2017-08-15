from datetime import datetime

from gino import Gino

db = Gino()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.BigInteger(), primary_key=True)
    profile = db.Column(db.JSONB())
    nickname = db.StringProperty(default='noname')
    age = db.IntegerProperty(default=18)
    birthday = db.DateTimeProperty()

    def __repr__(self):
        return f'Nickname: {self.nickname}, Age: {self.age}, ' \
               f'Birthday: {self.birthday}'


async def main():
    await db.create_pool('postgresql://localhost/gino')
    u = User()
    u.age += 10
    print('Pure in-memory object:', u)

    u = await User.create(nickname='fantix', birthday=datetime.utcnow())
    u.age += 1
    print('New user, default age taking effect:', u)

    u = await User.get(u.id)
    print('Reload from DB:', u)

    u.update(birthday=datetime.now())
    print('In memory update birthday:', u)

    await u.update(age=User.age - 2, nickname='daisy').apply()
    print('Applied update on age and nickname:', u)

    u = await User.get(u.id)
    print('Reload from DB:', u)

    print(await u.delete())


if __name__ == '__main__':
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
