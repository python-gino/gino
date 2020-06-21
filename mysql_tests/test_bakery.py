import pytest
import sqlalchemy

from gino import UninitializedError, create_engine, InitializedError
from gino.bakery import Bakery, BakedQuery
from .models import db, User, MYSQL_URL

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "query",
    [
        User.query.where(User.id == db.bindparam("uid")),
        sqlalchemy.text("SELECT * FROM gino_users WHERE id = :uid"),
        "SELECT * FROM gino_users WHERE id = :uid",
        lambda: User.query.where(User.id == db.bindparam("uid")),
        lambda: sqlalchemy.text("SELECT * FROM gino_users WHERE id = :uid"),
        lambda: "SELECT * FROM gino_users WHERE id = :uid",
    ],
)
@pytest.mark.parametrize("options", [dict(return_model=False), dict(loader=User)])
@pytest.mark.parametrize("api", [True, False])
@pytest.mark.parametrize("timeout", [None, 1])
async def test(query, options, sa_engine, api, timeout):
    uid = sa_engine.execute(User.insert()).lastrowid
    if timeout:
        options["timeout"] = timeout

    if api:
        b = db._bakery
        qs = [db.bake(query, **options)]
        if callable(query):
            qs.append(db.bake(**options)(query))
    else:
        b = Bakery()
        qs = [b.bake(query, **options)]
        if callable(query):
            qs.append(b.bake(**options)(query))

    for q in qs:
        assert isinstance(q, BakedQuery)
        assert q in list(b)
        assert q.sql is None
        assert q.compiled_sql is None

        with pytest.raises(UninitializedError):
            q.bind.first()
        with pytest.raises(UninitializedError):
            await q.first()

        for k, v in options.items():
            assert q.query.get_execution_options()[k] == v

    if api:
        e = await db.set_bind(MYSQL_URL, minsize=1)
    else:
        e = await create_engine(MYSQL_URL, bakery=b, minsize=1)

    with pytest.raises(InitializedError):
        b.bake("SELECT now()")

    with pytest.raises(InitializedError):
        await create_engine(MYSQL_URL, bakery=b, minsize=0)

    try:
        for q in qs:
            assert q.sql is not None
            assert q.compiled_sql is not None

            if api:
                assert q.bind is e
            else:
                with pytest.raises(UninitializedError):
                    q.bind.first()
                with pytest.raises(UninitializedError):
                    await q.first()

            if api:
                rv = await q.first(uid=uid)
            else:
                rv = await e.first(q, uid=uid)

            if options.get("return_model", True):
                assert isinstance(rv, User)
                assert rv.id == uid
            else:
                assert rv[0] == rv[User.id] == rv["id"] == uid

            eq = q.execution_options(return_model=True, loader=User)
            assert eq is not q
            assert isinstance(eq, BakedQuery)
            assert type(eq) is not BakedQuery
            assert eq in list(b)
            assert eq.sql == q.sql
            assert eq.compiled_sql is not q.compiled_sql

            if api:
                assert q.bind is e
            else:
                with pytest.raises(UninitializedError):
                    eq.bind.first()
                with pytest.raises(UninitializedError):
                    await eq.first()

            assert eq.query.get_execution_options()["return_model"]
            assert eq.query.get_execution_options()["loader"] is User

            if api:
                rv = await eq.first(uid=uid)
                non = await eq.first(uid=uid + 1)
                rvl = await eq.all(uid=uid)
            else:
                rv = await e.first(eq, uid=uid)
                non = await e.first(eq, uid=uid + 1)
                rvl = await e.all(eq, uid=uid)

            assert isinstance(rv, User)
            assert rv.id == uid

            assert non is None

            assert len(rvl) == 1
            assert rvl[0].id == uid

            # original query is not affected
            if api:
                rv = await q.first(uid=uid)
            else:
                rv = await e.first(q, uid=uid)

            if options.get("return_model", True):
                assert isinstance(rv, User)
                assert rv.id == uid
            else:
                assert rv[0] == rv[User.id] == rv["id"] == uid

    finally:
        if api:
            await db.pop_bind().close()
        else:
            await e.close()


async def test_class_level_bake():
    class BakeOnClass(db.Model):
        __tablename__ = "bake_on_class_test"

        name = db.Column(db.String(255), primary_key=True)

        @db.bake
        def getter(cls):
            return cls.query.where(cls.name == db.bindparam("name"))

    async with db.with_bind(MYSQL_URL, prebake=False, autocommit=True):
        await db.gino.create_all()
        try:
            await BakeOnClass.create(name="exist")
            assert (await BakeOnClass.getter.one(name="exist")).name == "exist"
            assert (await BakeOnClass.getter.one_or_none(name="nonexist")) is None
        finally:
            await db.gino.drop_all()
