from sqlalchemy import Column
from sqlalchemy.dialects.mysql import (
    DOUBLE as Double,
    INTEGER as Integer,
)

from ichnaea.models.base import (
    TimeTrackingMixin,
    PositionMixin,
)
from ichnaea.models.sa_types import TZDateTime as DateTime


class BaseStationMixin(PositionMixin, TimeTrackingMixin):

    range = Column(Integer)
    total_measures = Column(Integer(unsigned=True))


class StationMixin(BaseStationMixin):

    max_lat = Column(Double(asdecimal=False))
    min_lat = Column(Double(asdecimal=False))

    max_lon = Column(Double(asdecimal=False))
    min_lon = Column(Double(asdecimal=False))

    new_measures = Column(Integer(unsigned=True))


class StationBlacklistMixin(object):

    time = Column(DateTime)
    count = Column(Integer)
