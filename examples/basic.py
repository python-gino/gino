from gino import Gino, create_engine

db = Gino()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.BigInteger(), primary_key=True)
    nickname = db.Column(db.Unicode(), default='noname')
    profile = db.Column(db.JSONB())

    def __repr__(self):
        return '{}<{}>'.format(self.nickname, self.id)


async def main():
    # Database endpoint.
    db_endpoint = 'postgresql://localhost/gino'

    # In this example we create the database tables directly using SQLAlchemy
    # and non-async Postgres (uses psycopg2 python module, not asyncpg which
    # GINO uses). For a production application you would probably use a full
    # schema migration solution like Alembic.
    import sqlalchemy as sa
    db_engine = sa.create_engine(db_endpoint)
    db.create_all(bind=db_engine)
    db_engine.dispose()

    # Here starts the normal async application
    engine = await create_engine(db_endpoint)

    u = await User.create(bind=engine, nickname='fantix')
    print(u)
    print(await User.get(u.id, bind=engine))
    await u.update(nickname='daisy').apply(bind=engine)
    print(await User.get(u.id, bind=engine))
    await u.delete(bind=engine)
    print(await User.get(u.id, bind=engine))


if __name__ == '__main__':
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
