import pytest
import tornado.web
import tornado.httpclient
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.escape
from gino.ext.tornado import Gino, Application, GinoRequestHandler

from .models import DB_ARGS


# noinspection PyShadowingNames
@pytest.fixture
async def app():
    db = Gino()

    class User(db.Model):
        __tablename__ = 'users'

        id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
        nickname = db.Column(db.Unicode(), nullable=False)

    class AllUsers(GinoRequestHandler):
        async def get(self):
            import asyncio
            assert asyncio.Task.current_task() is not None

            users = await User.query.gino.all()

            for user in users:
                url = self.application.reverse_url('user', user.id)
                nickname = tornado.escape.xhtml_escape(user.nickname)
                self.write(f'<a href="{url}">{nickname}</a><br/>')

    class GetUser(GinoRequestHandler):
        async def get(self, uid):
            user: User = await User.get_or_404(int(uid))
            nickname = tornado.escape.xhtml_escape(user.nickname)
            self.write(f'Hi, {nickname}!')

    class AddUser(GinoRequestHandler):
        async def post(self):
            user = await User.create(nickname=self.get_argument('name'))
            nickname = tornado.escape.xhtml_escape(user.nickname)
            self.write(f'Hi, {nickname}!')

    options = {
        'db_host': DB_ARGS['host'],
        'db_port': DB_ARGS['port'],
        'db_user': DB_ARGS['user'],
        'db_password': DB_ARGS['password'],
        'db_database': DB_ARGS['database'],
    }
    for option, value in options.items():
        setattr(tornado.options.options, option, value)
    app = Application([
        tornado.web.URLSpec(r'/', AllUsers, name='index'),
        tornado.web.URLSpec(r'/user/(?P<uid>[0-9]+)', GetUser, name='user'),
        tornado.web.URLSpec(r'/user', AddUser, name='user_add'),
    ], debug=True)
    await app.late_init(db)
    await db.gino.create_all()
    try:
        yield app
    finally:
        await db.gino.drop_all()


# noinspection PyShadowingNames
@pytest.fixture
async def base_url(app: Application, unused_tcp_port):
    server = tornado.httpserver.HTTPServer(app)
    server.listen(unused_tcp_port)
    try:
        yield f'http://localhost:{unused_tcp_port}'
    finally:
        server.stop()


# noinspection PyShadowingNames
@pytest.fixture
def http_client():
    return tornado.httpclient.AsyncHTTPClient()


# noinspection PyShadowingNames
@pytest.mark.asyncio
async def test_hello_world(http_client, base_url):
    response = await http_client.fetch(base_url)
    assert response.code == 200

    with pytest.raises(tornado.httpclient.HTTPError, match='404'):
        await http_client.fetch(base_url + '/user/1')

    response = await http_client.fetch(base_url + '/user', method='POST',
                                       body='name=fantix')
    assert response.code == 200
    assert b'fantix' in response.body

    response = await http_client.fetch(base_url + '/user/1')
    assert response.code == 200
    assert b'fantix' in response.body

    response = await http_client.fetch(base_url)
    assert response.code == 200
    assert b'fantix' in response.body
