import gino
import pytest
from aiohttp import web
from async_generator import yield_, async_generator
from gino.ext.aiohttp import Gino

from .models import DB_ARGS, PG_URL

pytestmark = pytest.mark.asyncio
_MAX_INACTIVE_CONNECTION_LIFETIME = 59.0


# noinspection PyShadowingNames
async def _test_client(config, in_app_config=True):
    from aiohttp.test_utils import TestServer, TestClient

    db = Gino()
    app = web.Application(middlewares=[db])
    db_attr_name = 'gino_db'
    config.update({
        'kwargs': dict(
            max_inactive_connection_lifetime=_MAX_INACTIVE_CONNECTION_LIFETIME,
        ),
    })
    if in_app_config:
        app['config'] = dict(gino=config)
        db.init_app(app, db_attr_name=db_attr_name)
    else:
        db.init_app(app, config, db_attr_name=db_attr_name)

    class User(db.Model):
        __tablename__ = 'gino_users'

        id = db.Column(db.BigInteger(), primary_key=True)
        nickname = db.Column('name', db.Unicode(), default='noname')

    routes = web.RouteTableDef()

    @routes.get('/')
    async def root(request):
        conn = await request['connection'].get_raw_connection()
        # noinspection PyProtectedMember
        assert conn._holder._max_inactive_time == \
            _MAX_INACTIVE_CONNECTION_LIFETIME
        return web.Response(text='Hello, world!')

    @routes.get('/users/{uid}')
    async def get_user(request):
        uid = int(request.match_info['uid'])
        method = request.query.get('method')
        q = User.query.where(User.id == uid)
        if method == '1':
            return web.json_response((await q.gino.first_or_404()).to_dict())
        elif method == '2':
            return web.json_response(
                (await request['connection'].first_or_404(q)).to_dict())
        elif method == '3':
            return web.json_response(
                (await db.bind.first_or_404(q)).to_dict())
        elif method == '4':
            return web.json_response(
                (await request.app[db_attr_name].first_or_404(q)).to_dict())
        else:
            return web.json_response((await User.get_or_404(uid)).to_dict())

    @routes.post('/users')
    async def add_user(request):
        form = await request.post()
        u = await User.create(nickname=form.get('name'))
        await u.query.gino.first_or_404()
        await db.first_or_404(u.query)
        await db.bind.first_or_404(u.query)
        await request['connection'].first_or_404(u.query)
        return web.json_response(u.to_dict())

    app.router.add_routes(routes)

    e = await gino.create_engine(PG_URL)
    try:
        try:
            await db.gino.create_all(e)
            async with TestClient(TestServer(app)) as rv:
                await yield_(rv)
        finally:
            await db.gino.drop_all(e)
    finally:
        await e.close()


@pytest.fixture(params=[True, False])
@async_generator
async def test_client(request):
    await _test_client(DB_ARGS.copy(), request.param)


@pytest.fixture(params=[True, False])
@async_generator
async def test_client_dsn(request):
    await _test_client(dict(dsn=PG_URL), request.param)


@pytest.fixture(params=[True, False])
@async_generator
async def test_client_ssl(ssl_ctx, request):
    await _test_client(dict(dsn=PG_URL, ssl=ssl_ctx), request.param)


async def _test_index_returns_200(test_client):
    response = await test_client.get('/')
    assert response.status == 200
    assert await response.text() == 'Hello, world!'


async def test_index_returns_200(test_client):
    await _test_index_returns_200(test_client)


async def test_index_returns_200_dsn(test_client_dsn):
    await _test_index_returns_200(test_client_dsn)


async def _test(test_client):
    response = await test_client.get('/users/1')
    assert response.status == 404

    for method in '1234':
        response = await test_client.get('/users/1?method=' + method)
        assert response.status == 404

    response = await test_client.post('/users', data=dict(name='fantix'))
    assert response.status == 200
    assert await response.json() == dict(id=1, nickname='fantix')

    response = await test_client.get('/users/1')
    assert response.status == 200
    assert await response.json() == dict(id=1, nickname='fantix')


async def test(test_client):
    await _test(test_client)


async def test_dsn(test_client_dsn):
    await _test(test_client_dsn)


async def test_ssl(test_client_ssl):
    await _test(test_client_ssl)
