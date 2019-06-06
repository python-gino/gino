import asyncio

from async_generator import yield_, async_generator
import pytest
import sanic
from sanic.response import text, json

import gino
from gino.ext.sanic import Gino

from .models import DB_ARGS, PG_URL

_MAX_INACTIVE_CONNECTION_LIFETIME = 59.0


def teardown_module():
    # sanic server will close the loop during shutdown
    asyncio.set_event_loop(asyncio.new_event_loop())


# noinspection PyShadowingNames
async def _app(config):
    app = sanic.Sanic()
    app.config.update(config)
    app.config.update({
        'DB_KWARGS': dict(
            max_inactive_connection_lifetime=_MAX_INACTIVE_CONNECTION_LIFETIME,
        ),
    })

    db = Gino(app)

    class User(db.Model):
        __tablename__ = 'gino_users'

        id = db.Column(db.BigInteger(), primary_key=True)
        nickname = db.Column(db.Unicode(), default='noname')

    @app.route('/')
    async def root(request):
        conn = await request['connection'].get_raw_connection()
        # noinspection PyProtectedMember
        assert conn._holder._max_inactive_time == \
            _MAX_INACTIVE_CONNECTION_LIFETIME
        return text('Hello, world!')

    @app.route('/users/<uid:int>')
    async def get_user(request, uid):
        method = request.args.get('method')
        q = User.query.where(User.id == uid)
        if method == '1':
            return json((await q.gino.first_or_404()).to_dict())
        elif method == '2':
            return json(
                (await request['connection'].first_or_404(q)).to_dict())
        elif method == '3':
            return json(
                (await db.bind.first_or_404(q)).to_dict())
        elif method == '4':
            return json(
                (await db.first_or_404(q)).to_dict())
        else:
            return json((await User.get_or_404(uid)).to_dict())

    @app.route('/users', methods=['POST'])
    async def add_user(request):
        u = await User.create(nickname=request.form.get('name'))
        await u.query.gino.first_or_404()
        await db.first_or_404(u.query)
        await db.bind.first_or_404(u.query)
        await request['connection'].first_or_404(u.query)
        return json(u.to_dict())

    e = await gino.create_engine(PG_URL)
    try:
        try:
            await db.gino.create_all(e)
            await yield_(app)
        finally:
            await db.gino.drop_all(e)
    finally:
        await e.close()


@pytest.fixture
@async_generator
async def app():
    await _app({
        'DB_HOST': DB_ARGS['host'],
        'DB_PORT': DB_ARGS['port'],
        'DB_USER': DB_ARGS['user'],
        'DB_PASSWORD': DB_ARGS['password'],
        'DB_DATABASE': DB_ARGS['database'],
    })


@pytest.fixture
@async_generator
async def app_ssl(ssl_ctx):
    await _app({
        'DB_HOST': DB_ARGS['host'],
        'DB_PORT': DB_ARGS['port'],
        'DB_USER': DB_ARGS['user'],
        'DB_PASSWORD': DB_ARGS['password'],
        'DB_DATABASE': DB_ARGS['database'],
        'DB_SSL': ssl_ctx,
    })


@pytest.fixture
@async_generator
async def app_dsn():
    await _app({'DB_DSN': PG_URL})


def _test_index_returns_200(app):
    request, response = app.test_client.get('/')
    assert response.status == 200
    assert response.text == 'Hello, world!'


def test_index_returns_200(app):
    _test_index_returns_200(app)


def test_index_returns_200_dsn(app_dsn):
    _test_index_returns_200(app_dsn)


def _test(app):
    for method in '01234':
        request, response = app.test_client.get('/users/1?method=' + method)
        assert response.status == 404

    request, response = app.test_client.post('/users',
                                             data=dict(name='fantix'))
    assert response.status == 200
    assert response.json == dict(id=1, nickname='fantix')

    for method in '01234':
        request, response = app.test_client.get('/users/1?method=' + method)
        assert response.status == 200
        assert response.json == dict(id=1, nickname='fantix')


def test(app):
    _test(app)


def test_ssl(app_ssl):
    _test(app_ssl)


def test_dsn(app_dsn):
    _test(app_dsn)
