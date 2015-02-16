from sqlalchemy import (
    Column,
    Boolean,
    String,
)
from sqlalchemy.dialects.mysql import (
    INTEGER as Integer,
)

from ichnaea.models.base import _Model


class ApiKey(_Model):
    __tablename__ = 'api_key'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
    }

    valid_key = Column(String(40),
                       primary_key=True)

    # Maximum number of requests per day
    maxreq = Column(Integer)
    # Extended logging enabled?
    log = Column(Boolean)
    # A readable short name used in metrics
    shortname = Column(String(40))
    # A contact address
    email = Column(String(255))
    # Some free form context / description
    description = Column(String(255))


api_key_table = ApiKey.__table__
