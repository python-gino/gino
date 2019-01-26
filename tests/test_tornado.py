import pytest
import tornado.web
import tornado.httpclient
from tornado.ioloop import IOLoop
import tornado.options
import tornado.escape
from gino.ext.tornado import Gino, DBMixin, RequestHandlerMixin

from .models import DB_ARGS


# noinspection PyShadowingNames
@pytest.fixture
def app(ssl_ctx):
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

    class AllUsers(tornado.web.RequestHandler):
        async def get(self):
            users = await User.query.gino.all()

            for user in users:
                self.write('<a href="{url}">{nickname}</a><br/>'.format(
                    url=self.application.reverse_url('user', user.id),
                    nickname=tornado.escape.xhtml_escape(user.nickname)))

    class GetUser(tornado.web.RequestHandler, RequestHandlerMixin):
        async def get(self, uid):
            async with self.db.acquire() as conn:
                user = await User.get_or_404(int(uid), bind=conn)
                self.write('Hi, {}!'.format(user.nickname))

    class AddUser(tornado.web.RequestHandler):
        async def post(self):
            user = await User.create(nickname=self.get_argument('name'))
            self.write('Hi, {}!'.format(user.nickname))

    class Application(tornado.web.Application, DBMixin):
        pass

    app = Application([
        tornado.web.URLSpec(r'/', AllUsers, name='index'),
        tornado.web.URLSpec(r'/user/(?P<uid>[0-9]+)', GetUser, name='user'),
        tornado.web.URLSpec(r'/user', AddUser, name='user_add'),
    ], debug=True)
    IOLoop.current().run_sync(
        lambda: app.init_db(db, host=DB_ARGS['host'], port=DB_ARGS['port'],
                            user=DB_ARGS['user'],
                            password=DB_ARGS['password'],
                            database=DB_ARGS['database'],
                            max_inactive_connection_lifetime=59.0,
                            ssl=ssl_ctx))
    loop = tornado.ioloop.IOLoop.current().asyncio_loop
    loop.run_until_complete(db.gino.create_all())
    try:
        # noinspection PyProtectedMember
        assert app.db.bind._pool._pool._holders[0]._max_inactive_time == 59.0
        yield app
    finally:
        loop.run_until_complete(db.gino.drop_all())


@pytest.mark.gen_test
def test_hello_world(http_client, base_url):
    response = yield http_client.fetch(base_url)
    assert response.code == 200

    with pytest.raises(tornado.httpclient.HTTPClientError, match='404'):
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
