from enum import Enum

import pytest

import gino
from gino.dialects.aiomysql import AsyncEnum

pytestmark = pytest.mark.asyncio
db = gino.Gino()


class MyEnum(Enum):
    ONE = "one"
    TWO = "two"


class Blog(db.Model):
    __tablename__ = "s_blog"

    id = db.Column(db.BigInteger(), primary_key=True)
    title = db.Column(db.Unicode(255), index=True, comment="Title Comment")
    visits = db.Column(db.BigInteger(), default=0)
    comment_id = db.Column(db.ForeignKey("s_comment.id"))
    number = db.Column(db.Enum(MyEnum), nullable=False, default=MyEnum.TWO)
    number2 = db.Column(AsyncEnum(MyEnum), nullable=False, default=MyEnum.TWO)


class Comment(db.Model):
    __tablename__ = "s_comment"

    id = db.Column(db.BigInteger(), primary_key=True)
    blog_id = db.Column(db.ForeignKey("s_blog.id", name="blog_id_fk"))


blog_seq = db.Sequence("blog_seq", metadata=db, schema="schema_test")


async def test(engine, define=True):
    async with engine.acquire() as conn:
        assert not await engine.dialect.has_table(conn, "non_exist")
    Blog.__table__.comment = "Blog Comment"
    db.bind = engine
    await db.gino.create_all()
    await Blog.number.type.create_async(engine, checkfirst=True)
    await Blog.number2.type.create_async(engine, checkfirst=True)
    await db.gino.create_all(tables=[Blog.__table__], checkfirst=True)
    await blog_seq.gino.create(checkfirst=True)
    await Blog.__table__.gino.create(checkfirst=True)
    await db.gino.drop_all()
    await db.gino.drop_all(tables=[Blog.__table__], checkfirst=True)
    await Blog.__table__.gino.drop(checkfirst=True)
    await blog_seq.gino.drop(checkfirst=True)

    if define:

        class Comment2(db.Model):
            __tablename__ = "s_comment_2"

            id = db.Column(db.BigInteger(), primary_key=True)
            blog_id = db.Column(db.ForeignKey("s_blog.id"))

    await db.gino.create_all()
    await db.gino.drop_all()
