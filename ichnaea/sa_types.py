from sqlalchemy.types import TypeDecorator
from sqlalchemy.dialects.mysql import DATETIME as DateTime
from datetime import datetime
import time
import pytz


class TZDateTime(TypeDecorator):
    """Safely coerce Python bytestrings to Unicode
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
