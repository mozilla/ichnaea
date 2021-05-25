from datetime import datetime
from zoneinfo import ZoneInfo
import time

from enum import IntEnum
from sqlalchemy import String
from sqlalchemy.dialects.mysql import DATETIME as DateTime, TINYINT as TinyInteger
from sqlalchemy.types import TypeDecorator


class SetColumn(TypeDecorator):
    """
    A SetColumn stores a Python set of Unicode strings,
    as a comma separated string.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = ",".join([v for v in frozenset(value)])
        return value

    def process_result_value(self, value, dialect):
        if value == "":
            value = frozenset()
        elif value is not None:
            value = frozenset(value.split(","))
        return value


class TinyIntEnum(TypeDecorator):
    """An IntEnum type stores enum values as tiny integers."""

    impl = TinyInteger
    cache_ok = True

    def __init__(self, enum, *args, **kw):
        self.enum = enum
        TypeDecorator.__init__(self, *args, **kw)

    def process_bind_param(self, value, dialect):
        if isinstance(value, IntEnum):
            value = int(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = self.enum(value)
        return value


class TZDateTime(TypeDecorator):
    """
    Safely coerce Python datetime objects with timezone data
    before passing them off to the database.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if isinstance(value, datetime) and value.tzinfo is not None:
            value = value.replace(tzinfo=None)
            value = datetime.fromtimestamp(time.mktime(value.timetuple()))
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            ts = time.mktime(value.timetuple())
            value = datetime.fromtimestamp(ts).replace(tzinfo=ZoneInfo("UTC"))
        return value
