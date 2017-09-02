#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages, Extension
from pkg_resources import resource_filename

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    'asyncpg~=0.12',
    'SQLAlchemy~=1.1',
]

setup_requirements = [
    'Cython>=0.24',
    'pytest-runner',
]

test_requirements = [
    'pytest',
    'pytest-asyncio',
    'psycopg2',
]


class LazyExtension(Extension):
    def __init__(self, *args, **kwargs):
        self._include_dirs = []
        super().__init__(*args, **kwargs)

    @property
    def include_dirs(self):
        return self._include_dirs + [resource_filename('asyncpg', 'protocol')]

    @include_dirs.setter
    def include_dirs(self, val):
        self._include_dirs = val


setup(
    name='gino',
    version='0.4.1',
    description="GINO Is Not ORM - "
                "a Python ORM on asyncpg and SQLAlchemy core.",
    long_description=readme + '\n\n' + history,
    author="Fantix King",
    author_email='fantix.king@gmail.com',
    url='https://github.com/fantix/gino',
    packages=find_packages(),
    ext_modules=[
        LazyExtension('gino.record', ['gino/record.pyx']),
    ],
    include_package_data=True,
    install_requires=requirements,
    license="BSD license",
    zip_safe=False,
    keywords='gino',
    classifiers=[
        'Development Status :: 3 - Alpha',
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
