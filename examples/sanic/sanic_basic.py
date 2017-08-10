import asyncpg

from gino import Gino
from sanic import Sanic
from sanic.response import text
from sqlalchemy import Column, BigInteger, Unicode

app = Sanic()
app.config['GINO_USER'] = 'lbhsot'
app.config.GINO_DATABASE = 'gino'
db = Gino()
db.init_app(app)


class User(db.Model):
    __tablename__ = 'users'

    id = Column(BigInteger(), primary_key=True)
    nickname = Column(Unicode(), default='noname')

    def __repr__(self):
        return '{}<{}>'.format(self.nickname, self.id)


@app.route("/")
async def index(request):
    print(await User.get(6))
    print(await User.get_or_404(5))
    return text("Hello World!")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
