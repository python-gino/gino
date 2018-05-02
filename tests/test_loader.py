import random
from datetime import datetime

import pytest
from async_generator import yield_, async_generator

from .models import db, User, Team, Company

pytestmark = pytest.mark.asyncio


@pytest.fixture
@async_generator
async def user(bind, random_name):
    c = await Company.create()
    t1 = await Team.create(company_id=c.id)
    t2 = await Team.create(company_id=c.id, parent_id=t1.id)
    u = await User.create(nickname=random_name, team_id=t2.id)
    u.team = t2
    t2.parent = t1
    t2.company = c
    t1.company = c
    await yield_(u)
    await User.delete.gino.status()
    await Team.delete.gino.status()
    await Company.delete.gino.status()


async def test_model_alternative(user):
    u = await User.query.gino.load(User).first()
    assert isinstance(u, User)
    assert u.id == user.id
    assert u.nickname == user.nickname


async def test_scalar(user):
    name = await User.query.gino.load(User.nickname).first()
    assert user.nickname == name

    uid, name = await User.query.gino.load((User.id, User.nickname)).first()
    assert user.id == uid
    assert user.nickname == name


async def test_model_load(user):
    u = await User.query.gino.load(User.load('nickname')).first()
    assert isinstance(u, User)
    assert u.id is None
    assert u.nickname == user.nickname


async def test_216_model_load_passive_partial(user):
    u = await db.select([User.nickname]).gino.model(User).first()
    assert isinstance(u, User)
    assert u.id is None
    assert u.nickname == user.nickname


async def test_load_relationship(user):
    u = await User.outerjoin(Team).select().gino.load(
        User.load(team=Team)).first()
    assert isinstance(u, User)
    assert u.id == user.id
    assert u.nickname == user.nickname
    assert isinstance(u.team, Team)
    assert u.team.id == user.team.id
    assert u.team.name == user.team.name


async def test_load_nested(user):
    for u in (
        await User.outerjoin(Team).outerjoin(Company).select().gino.load(
            User.load(team=Team.load(company=Company))).first(),
        await User.load(team=Team.load(company=Company)).gino.first(),
        await User.load(team=Team.load(company=Company.on(
                Team.company_id == Company.id))).gino.first(),
        await User.load(team=Team.load(company=Company).on(
                User.team_id == Team.id)).gino.first(),
        await User.load(team=Team.on(User.team_id == Team.id).load(
            company=Company)).gino.first(),
    ):
        assert isinstance(u, User)
        assert u.id == user.id
        assert u.nickname == user.nickname
        assert isinstance(u.team, Team)
        assert u.team.id == user.team.id
        assert u.team.name == user.team.name
        assert isinstance(u.team.company, Company)
        assert u.team.company.id == user.team.company.id
        assert u.team.company.name == user.team.company.name


async def test_func(user):
    def loader(row, context):
        rv = User(id=row[User.id], nickname=row[User.nickname])
        rv.team = Team(id=row[Team.id], name=row[Team.name])
        rv.team.company = Company(id=row[Company.id], name=row[Company.name])
        return rv

    u = await User.outerjoin(Team).outerjoin(Company).select().gino.load(
        loader).first()
    assert isinstance(u, User)
    assert u.id == user.id
    assert u.nickname == user.nickname
    assert isinstance(u.team, Team)
    assert u.team.id == user.team.id
    assert u.team.name == user.team.name
    assert isinstance(u.team.company, Company)
    assert u.team.company.id == user.team.company.id
    assert u.team.company.name == user.team.company.name


async def test_adjacency_list(user):
    group = Team.alias()

    with pytest.raises(AttributeError):
        group.non_exist()

    # noinspection PyUnusedLocal
    def loader(row, context):
        rv = User(id=row[User.id], nickname=row[User.nickname])
        rv.team = Team(id=row[Team.id], name=row[Team.name])
        rv.team.parent = Team(id=row[group.id], name=row[group.name])
        return rv

    for exp in (loader,
                User.load(team=Team.load(parent=group)),
                User.load(team=Team.load(parent=group.load('id', 'name'))),
                User.load(team=Team.load(parent=group.load()))):
        u = await User.outerjoin(
            Team
        ).outerjoin(
            group, Team.parent_id == group.id
        ).select().gino.load(exp).first()

        assert isinstance(u, User)
        assert u.id == user.id
        assert u.nickname == user.nickname
        assert isinstance(u.team, Team)
        assert u.team.id == user.team.id
        assert u.team.name == user.team.name
        assert isinstance(u.team.parent, Team)
        assert u.team.parent.id == user.team.parent.id
        assert u.team.parent.name == user.team.parent.name


async def test_adjacency_list_query_builder(user):
    group = Team.alias()
    u = await User.load(team=Team.load(parent=group.on(
        Team.parent_id == group.id))).gino.first()

    assert isinstance(u, User)
    assert u.id == user.id
    assert u.nickname == user.nickname
    assert isinstance(u.team, Team)
    assert u.team.id == user.team.id
    assert u.team.name == user.team.name
    assert isinstance(u.team.parent, Team)
    assert u.team.parent.id == user.team.parent.id
    assert u.team.parent.name == user.team.parent.name


async def test_literal(user):
    sample = tuple(random.random() for _ in range(5))
    now = db.Column('time', db.DateTime())
    row = await db.first(db.text(
        'SELECT now() AT TIME ZONE \'UTC\''
    ).columns(now).gino.load(
        sample + (lambda r, c: datetime.utcnow(), now,)).query)
    assert row[:5] == sample
    assert isinstance(row[-2], datetime)
    assert isinstance(row[-1], datetime)
    assert row[-1] <= row[-2]
