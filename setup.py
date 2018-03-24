#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()


def req_file(filename):
    with open(filename) as f:
        content = f.readlines()
    return [x.strip() for x in content if x.strip()]


setup_requirements = [
    'pytest-runner',
]

test_requirements = [
    'pytest',
    'pytest-asyncio',
    'pytest-mock',
    'psycopg2-binary',
]

setup(
    name='gino',
    version='0.6.2',
    description="GINO Is Not ORM - "
                "a Python asyncio ORM on SQLAlchemy core.",
    long_description=readme + '\n\n' + history,
    author="Fantix King",
    author_email='fantix.king@gmail.com',
    url='https://github.com/fantix/gino',
    packages=[p for p in find_packages() if p != 'tests'],
    include_package_data=True,
    install_requires=req_file('requirements.txt'),
    entry_points="""
    [sqlalchemy.dialects]
    postgresql.asyncpg = gino.dialects.asyncpg:AsyncpgDialect
    asyncpg = gino.dialects.asyncpg:AsyncpgDialect
    """,
    license="BSD license",
    zip_safe=False,
    keywords='gino',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
    test_suite='tests',
    tests_require=test_requirements,
    setup_requires=setup_requirements,
)
