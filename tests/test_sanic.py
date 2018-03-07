import gino
import sanic
import pytest
from sanic.response import text, json
from gino.ext.sanic import Gino

from .models import DB_ARGS, PG_URL


# noinspection PyShadowingNames
@pytest.fixture
async def app():
    app = sanic.Sanic()
    app.config['DB_HOST'] = DB_ARGS['host']
    app.config['DB_PORT'] = DB_ARGS['port']
    app.config['DB_USER'] = DB_ARGS['user']
    app.config['DB_PASSWORD'] = DB_ARGS['password']
    app.config['DB_DATABASE'] = DB_ARGS['database']

    db = Gino(app)

    class User(db.Model):
        __tablename__ = 'gino_users'

        id = db.Column(db.BigInteger(), primary_key=True)
        nickname = db.Column(db.Unicode(), default='noname')

    @app.route('/')
    async def root(request):
        return text('Hello, world!')

    @app.route('/users/<uid:int>')
    async def get_user(request, uid):
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
            yield app
        finally:
            await db.gino.drop_all(e)
    finally:
        await e.close()


def test_index_returns_200(app):
    request, response = app.test_client.get('/')
    assert response.status == 200
    assert response.text == 'Hello, world!'


def test(app):
    request, response = app.test_client.get('/users/1')
    assert response.status == 404

    request, response = app.test_client.post('/users',
                                             data=dict(name='fantix'))
    assert response.status == 200
    assert response.json == dict(id=1, nickname='fantix')

    request, response = app.test_client.get('/users/1')
    assert response.status == 200
    assert response.json == dict(id=1, nickname='fantix')
