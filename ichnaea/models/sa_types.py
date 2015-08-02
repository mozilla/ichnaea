from base64 import (
    b16decode,
    b16encode,
)
from datetime import datetime
import time

from enum import IntEnum
import pytz
from sqlalchemy import BINARY
from sqlalchemy.dialects.mysql import (
    DATETIME as DateTime,
    TINYINT as TinyInteger,
)
from sqlalchemy.types import TypeDecorator


class MacColumn(TypeDecorator):
    """A binary type storing MAC's."""

    impl = BINARY

    def process_bind_param(self, value, dialect):
        if not (value and len(value) == 12):
            raise ValueError('Invalid MAC: %r' % value)
        return b16decode(value, casefold=True)

    def process_result_value(self, value, dialect):
        return b16encode(value).decode('ascii')


class TinyIntEnum(TypeDecorator):
    """An IntEnum type storing values as tiny integers."""

    impl = TinyInteger

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
    """Safely coerce Python datetime with timezone data
    before passing off to the database."""

    impl = DateTime

    def process_bind_param(self, value, dialect):
        if isinstance(value, datetime):
            value = value.replace(tzinfo=None)
            value = datetime.fromtimestamp(time.mktime(value.timetuple()))
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            ts = time.mktime(value.timetuple())
            value = datetime.fromtimestamp(ts).replace(tzinfo=pytz.UTC)
        return value
