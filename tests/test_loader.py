import random
from datetime import datetime

from async_generator import yield_, async_generator
import pytest
from sqlalchemy import select
from sqlalchemy.sql.functions import count

from gino.loader import AliasLoader
from .models import db, User, Team, Company

pytestmark = pytest.mark.asyncio


@pytest.fixture
@async_generator
async def user(bind):
    c = await Company.create()
    t1 = await Team.create(company_id=c.id)
    t2 = await Team.create(company_id=c.id, parent_id=t1.id)
    u = await User.create(team_id=t2.id)
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
    u = await User.query.gino.load(User.load('nickname', User.team_id)).first()
    assert isinstance(u, User)
    assert u.id is None
    assert u.nickname == user.nickname
    assert u.team_id == user.team.id

    with pytest.raises(TypeError):
        await User.query.gino.load(User.load(123)).first()

    with pytest.raises(AttributeError):
        await User.query.gino.load(User.load(Team.id)).first()


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


async def test_alias_loader_columns(user):
    user_alias = User.alias()
    base_query = user_alias.outerjoin(Team).select()

    query = base_query.execution_options(loader=AliasLoader(user_alias, 'id'))
    u = await query.gino.first()
    assert u.id is not None


async def test_multiple_models_in_one_query(bind):
    for _ in range(3):
        await User.create()

    ua1 = User.alias()
    ua2 = User.alias()
    join_query = select([ua1, ua2]).where(ua1.id < ua2.id)
    result = await join_query.gino.load((ua1.load('id'), ua2.load('id'))).all()
    assert len(result) == 3
    for u1, u2 in result:
        assert u1.id is not None
        assert u2.id is not None
        assert u1.id < u2.id


async def test_loader_with_aggregation(user):
    count_col = count().label('count')
    user_count = select(
        [User.team_id, count_col]
    ).group_by(
        User.team_id
    ).alias()
    query = Team.outerjoin(user_count).select()
    result = await query.gino.load(
        (Team.id, Team.name, user_count.columns.team_id, count_col)
    ).all()
    assert len(result) == 2
    # team 1 doesn't have users, team 2 has 1 user
    # third and forth columns are None for team 1
    for team_id, team_name, user_team_id, user_count in result:
        if team_id == user.team_id:
            assert team_name == user.team.name
            assert user_team_id == user.team_id
            assert user_count == 1
        else:
            assert team_id is not None
            assert team_name is not None
            assert user_team_id is None
            assert user_count is None


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


async def test_load_one_to_many(user):
    # noinspection PyListCreation
    uids = [user.id]
    uids.append((await User.create(nickname='1', team_id=user.team.id)).id)
    uids.append((await User.create(nickname='1', team_id=user.team.id)).id)
    uids.append((await User.create(nickname='2',
                                   team_id=user.team.parent.id)).id)
    query = User.outerjoin(Team).outerjoin(Company).select()
    companies = await query.gino.load(
        Company.distinct(Company.id).load(
            add_team=Team.load(add_member=User).distinct(Team.id))).all()
    assert len(companies) == 1
    company = companies[0]
    assert isinstance(company, Company)
    assert company.id == user.team.company_id
    assert company.name == user.team.company.name
    assert len(company.teams) == 2
    for team in company.teams:
        if team.id == user.team.id:
            assert len(team.members) == 3
            for u in team.members:
                if u.nickname == user.nickname:
                    assert isinstance(u, User)
                    assert u.id == user.id
                    uids.remove(u.id)
                if u.nickname in {'1', '2'}:
                    uids.remove(u.id)
        else:
            assert len(team.members) == 1
            uids.remove(list(team.members)[0].id)
    assert uids == []

    # test distinct many-to-one
    query = User.outerjoin(Team).select().where(Team.id == user.team.id)
    users = await query.gino.load(
        User.load(team=Team.distinct(Team.id))).all()
    assert len(users) == 3
    assert users[0].team is users[1].team
    assert users[0].team is users[2].team


async def test_distinct_none(bind):
    u = await User.create()

    query = User.outerjoin(Team).select().where(User.id == u.id)
    loader = User.load(team=Team.none_as_none(False))

    # TODO: this should fail in 1.0, please remove by then
    u = await query.gino.load(loader).first()
    assert u.team.id is None

    query = User.outerjoin(Team).select().where(User.id == u.id)
    loader = User.load(team=Team)

    u = await query.gino.load(loader).first()
    assert not hasattr(u, 'team')

    u = await User.load(team=Team).query.where(User.id == u.id).gino.first()
    assert not hasattr(u, 'team')

    query = User.outerjoin(Team).select().where(User.id == u.id)
    loader = User.load(team=Team.distinct(Team.id))

    u = await query.gino.load(loader).first()
    assert not hasattr(u, 'team')


async def test_tuple_loader_279(user):
    from gino.loader import TupleLoader
    query = db.select([User, Team])
    async with db.transaction():
        async for row in query.gino.load((User, Team)).iterate():
            assert len(row) == 2
        async for row in query.gino.load(TupleLoader((User, Team))).iterate():
            assert len(row) == 2


async def test_none_as_none_281(user):
    import gino

    if gino.__version__ < '0.9':
        query = Team.outerjoin(User).select()
        loader = Team, User.none_as_none()
        assert any(row[1] is None
                   for row in await query.gino.load(loader).all())

        loader = Team.distinct(Team.id).load(add_member=User.none_as_none())
        assert any(not team.members
                   for team in await query.gino.load(loader).all())

    if gino.__version__ >= '0.8.0':
        query = Team.outerjoin(User).select()
        loader = Team, User
        assert any(row[1] is None
                   for row in await query.gino.load(loader).all())

        loader = Team.distinct(Team.id).load(add_member=User)
        assert any(not team.members
                   for team in await query.gino.load(loader).all())
