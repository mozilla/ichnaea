from datetime import datetime
from pytz import UTC


def utcnow():
    return datetime.utcnow().replace(microsecond=0, tzinfo=UTC)
