from enum import Enum

import pytest

import gino
from gino.dialects.asyncpg import AsyncEnum

pytestmark = pytest.mark.asyncio
db = gino.Gino()


class MyEnum(Enum):
    ONE = 'one'
    TWO = 'two'


class Blog(db.Model):
    __tablename__ = 's_blog'

    id = db.Column(db.BigInteger(), primary_key=True)
    title = db.Column(db.Unicode(), index=True, comment='Title Comment')
    visits = db.Column(db.BigInteger(), default=0)
    comment_id = db.Column(db.ForeignKey('s_comment.id'))
    number = db.Column(db.Enum(MyEnum), nullable=False, default=MyEnum.TWO)
    number2 = db.Column(AsyncEnum(MyEnum), nullable=False, default=MyEnum.TWO)


class Comment(db.Model):
    __tablename__ = 's_comment'

    id = db.Column(db.BigInteger(), primary_key=True)
    blog_id = db.Column(db.ForeignKey('s_blog.id', name='blog_id_fk'))


blog_seq = db.Sequence('blog_seq', metadata=db, schema='schema_test')


async def test(engine, define=True):
    try:
        async with engine.acquire() as conn:
            assert not await engine.dialect.has_schema(conn, 'schema_test')
            assert not await engine.dialect.has_table(conn, 'non_exist')
            assert not await engine.dialect.has_sequence(conn, 'non_exist')
            assert not await engine.dialect.has_type(conn, 'non_exist')
            assert not await engine.dialect.has_type(conn, 'non_exist',
                                                     schema='schema_test')
        await engine.status('create schema schema_test')
        Blog.__table__.schema = 'schema_test'
        Blog.__table__.comment = 'Blog Comment'
        Comment.__table__.schema = 'schema_test'
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
                __tablename__ = 's_comment_2'

                id = db.Column(db.BigInteger(), primary_key=True)
                blog_id = db.Column(db.ForeignKey('s_blog.id'))

            Comment2.__table__.schema = 'schema_test'
        await db.gino.create_all()
        await db.gino.drop_all()
    finally:
        await engine.status('drop schema schema_test cascade')


async def test_no_alter(engine, mocker):
    engine.dialect.supports_alter = False
    warn = mocker.patch('warnings.warn')
    await test(engine, define=False)
    assert warn.called
