import pytest
import tornado.web
import tornado.httpclient
import tornado.ioloop
import tornado.options
import tornado.escape
from gino.ext.tornado import Gino, Application, GinoRequestHandler


# noinspection PyShadowingNames
@pytest.fixture
def app():
    # Define your database metadata
    # -----------------------------

    db = Gino()

    # Define tables as you would normally do
    # --------------------------------------

    class User(db.Model):
        __tablename__ = 'users'

        id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
        nickname = db.Column(db.Unicode(), nullable=False)

    # Now just use your tables
    # ------------------------

    class AllUsers(GinoRequestHandler):
        async def get(self):
            users = await User.query.gino.all()

            for user in users:
                url = self.application.reverse_url('user', user.id)
                nickname = tornado.escape.xhtml_escape(user.nickname)
                self.write(f'<a href="{url}">{nickname}</a><br/>')

    class GetUser(GinoRequestHandler):
        async def get(self, uid):
            user: User = await User.get_or_404(int(uid))
            self.write(f'Hi, {user.nickname}!')

    class AddUser(GinoRequestHandler):
        async def post(self):
            user = await User.create(nickname=self.get_argument('name'))
            self.write(f'Hi, {user.nickname}!')

    app = Application([
        tornado.web.URLSpec(r'/', AllUsers, name='index'),
        tornado.web.URLSpec(r'/user/(?P<uid>[0-9]+)', GetUser, name='user'),
        tornado.web.URLSpec(r'/user', AddUser, name='user_add'),
    ], debug=True)
    loop = tornado.ioloop.IOLoop.current().asyncio_loop
    loop.run_until_complete(app.late_init(db))
    loop.run_until_complete(db.gino.create_all())
    try:
        yield app
    finally:
        loop.run_until_complete(db.gino.drop_all())


@pytest.fixture
async def io_loop(event_loop):
    from tornado.platform.asyncio import AsyncIOMainLoop
    return AsyncIOMainLoop()


@pytest.mark.gen_test
def test_hello_world(http_client, base_url):
    response = yield http_client.fetch(base_url)
    assert response.code == 200

    with pytest.raises(tornado.httpclient.HTTPError, match='404'):
        yield http_client.fetch(base_url + '/user/1')

    response = yield http_client.fetch(base_url + '/user', method='POST',
                                       body='name=fantix')
    assert response.code == 200
    assert b'fantix' in response.body

    response = yield http_client.fetch(base_url + '/user/1')
    assert response.code == 200
    assert b'fantix' in response.body

    response = yield http_client.fetch(base_url)
    assert response.code == 200
    assert b'fantix' in response.body
