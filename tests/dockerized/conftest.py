import asyncio
import time

import docker
import psycopg2
import pytest
from sqlalchemy import create_engine

from tests.dockerized.models import db


HOST_DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'user': 'postgres',
    'password': '',
    'database': 'postgres',
}
CONTAINER_DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'gino',
    'password': 'gino',
    'database': 'gino',
}
DSN = 'postgresql://{user}:{password}@{host}:{port}/{database}'
HOST_DB_URL = DSN.format(**HOST_DB_CONFIG)
CONTAINER_DB_URL = DSN.format(**CONTAINER_DB_CONFIG)


@pytest.fixture(scope='session')
def docker_client():
    return docker.from_env()


def wait_for_container(image):
    print(f"Waiting for `{image}` container to accept connections")
    delay = 0.001
    for i in range(100):
        try:
            conn = psycopg2.connect(HOST_DB_URL)
            cur = conn.cursor()
            cur.close()
            conn.close()
        except psycopg2.Error:
            time.sleep(delay)
            delay *= 2
        else:
            print(f"Container for `{image}` is ready")
            break
    else:
        raise RuntimeError('Cannot connect to container for `{image}`')


@pytest.fixture(scope='session')
def pg_server(docker_client):
    tag = 9.6
    # tag = 10.1
    image = f'postgres:{tag}'

    existing_images = []
    for im in docker_client.images.list():
        if im.tags:
            existing_images.append(im.tags[0])

    existing_images = [im.tags[0] for im in docker_client.images.list() if im.tags]

    if image in existing_images:
        print(f'`{image}` image exists')
    else:
        print(f'Pulling new `{image}` image...')
        docker_client.images.pull(image)

    internal_port = CONTAINER_DB_CONFIG['port']
    host_port = HOST_DB_CONFIG['port']

    container = docker_client.containers.run(
        image=image,
        name='test-postgres',
        detach=True,
        ports={internal_port: host_port}
    )

    print('Created containers: ', docker_client.containers.list())
    wait_for_container(image)

    yield

    container.kill()
    container.remove()


def setup_db(engine, target_config):

    db_name = target_config['database']
    db_user = target_config['user']
    db_pass = target_config['password']

    with engine.connect() as conn:
        conn.execute("CREATE USER %s WITH PASSWORD '%s'" % (db_user, db_pass))
        conn.execute("CREATE DATABASE %s" % db_name)
        conn.execute("GRANT ALL PRIVILEGES ON DATABASE %s TO %s" %
                     (db_name, db_user))

def teardown_db(engine, target_config):

    db_name = target_config['database']
    db_user = target_config['user']

    with engine.connect() as conn:
        # terminate all connections to be able to drop database
        conn.execute("""
          SELECT pg_terminate_backend(pg_stat_activity.pid)
          FROM pg_stat_activity
          WHERE pg_stat_activity.datname = '%s'
            AND pid <> pg_backend_pid();""" % db_name)

        conn.execute("DROP DATABASE IF EXISTS %s" % db_name)
        conn.execute("DROP ROLE IF EXISTS %s" % db_user)


@pytest.fixture(scope='module')
def pg_engine(pg_server):
    engine = create_engine(HOST_DB_URL, isolation_level='AUTOCOMMIT')
    return engine


@pytest.fixture(scope='module')
def db_setup(pg_server, pg_engine):
    setup_db(pg_engine, CONTAINER_DB_CONFIG)
    yield
    teardown_db(pg_engine, CONTAINER_DB_CONFIG)


@pytest.fixture(scope='session')
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='module')
def db_schema(db_setup, pg_engine, event_loop):
    event_loop.run_until_complete(db.set_bind(HOST_DB_URL))
    db.create_all(pg_engine)
    yield
    db.drop_all(pg_engine)
