import sys

import pytest

# Starlette only supports Python 3.6 or later
if sys.version_info < (3, 6):
    raise pytest.skip(allow_module_level=True)

from async_generator import yield_, async_generator
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.testclient import TestClient

import gino
from gino.ext.starlette import Gino

from .models import DB_ARGS, PG_URL

_MAX_INACTIVE_CONNECTION_LIFETIME = 59.0


# noinspection PyShadowingNames
async def _app(**kwargs):
    app = Starlette()
    kwargs.update({
        'kwargs': dict(
            max_inactive_connection_lifetime=_MAX_INACTIVE_CONNECTION_LIFETIME,
        ),
    })
    db = Gino(app, **kwargs)

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
        return PlainTextResponse('Hello, world!')

    @app.route('/users/{uid:int}')
    async def get_user(request):
        uid = request.path_params.get('uid')
        method = request.query_params.get('method')
        q = User.query.where(User.id == uid)
        if method == '1':
            return JSONResponse((await q.gino.first_or_404()).to_dict())
        elif method == '2':
            return JSONResponse(
                (await request['connection'].first_or_404(q)).to_dict())
        elif method == '3':
            return JSONResponse(
                (await db.bind.first_or_404(q)).to_dict())
        elif method == '4':
            return JSONResponse(
                (await db.first_or_404(q)).to_dict())
        else:
            return JSONResponse((await User.get_or_404(uid)).to_dict())

    @app.route('/users', methods=['POST'])
    async def add_user(request):
        u = await User.create(nickname=(await request.json()).get('name'))
        await u.query.gino.first_or_404()
        await db.first_or_404(u.query)
        await db.bind.first_or_404(u.query)
        await request['connection'].first_or_404(u.query)
        return JSONResponse(u.to_dict())

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
    await _app(
        host=DB_ARGS['host'],
        port=DB_ARGS['port'],
        user=DB_ARGS['user'],
        password=DB_ARGS['password'],
        database=DB_ARGS['database'],
    )


@pytest.fixture
@async_generator
async def app_ssl(ssl_ctx):
    await _app(
        host=DB_ARGS['host'],
        port=DB_ARGS['port'],
        user=DB_ARGS['user'],
        password=DB_ARGS['password'],
        database=DB_ARGS['database'],
        ssl=ssl_ctx,
    )


@pytest.fixture
@async_generator
async def app_dsn():
    await _app(dsn=PG_URL)


def _test_index_returns_200(app):
    client = TestClient(app)
    with client:
        response = client.get('/')
        assert response.status_code == 200
        assert response.text == 'Hello, world!'


def test_index_returns_200(app):
    _test_index_returns_200(app)


def test_index_returns_200_dsn(app_dsn):
    _test_index_returns_200(app_dsn)


def _test(app):
    client = TestClient(app)
    with client:
        for method in '01234':
            response = client.get('/users/1?method=' + method)
            assert response.status_code == 404

        response = client.post('/users', json=dict(name='fantix'))
        assert response.status_code == 200
        assert response.json() == dict(id=1, nickname='fantix')

        for method in '01234':
            response = client.get('/users/1?method=' + method)
            assert response.status_code == 200
            assert response.json() == dict(id=1, nickname='fantix')


def test(app):
    _test(app)


def test_ssl(app_ssl):
    _test(app_ssl)


def test_dsn(app_dsn):
    _test(app_dsn)
