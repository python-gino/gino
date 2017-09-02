cimport cpython

from asyncpg import Record
from asyncpg.protocol.record cimport ApgRecord_SET_ITEM


def update_record(record, i, val):
    assert isinstance(record, Record), 'asyncpg.Record is required'
    cpython.Py_DECREF(record[i])
    cpython.Py_INCREF(val)
    ApgRecord_SET_ITEM(record, i, val)
