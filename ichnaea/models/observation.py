from sqlalchemy import (
    Column,
    Float,
    Index,
)
from sqlalchemy.dialects.mysql import (
    INTEGER as Integer,
    SMALLINT as SmallInteger,
    TINYINT as TinyInteger,
)

from ichnaea.models.base import (
    _Model,
    BigIdMixin,
    PositionMixin,
)
from ichnaea.models.cell import CellKeyPscMixin
from ichnaea.models.wifi import WifiKeyMixin
from ichnaea.models.sa_types import (
    TZDateTime as DateTime,
    UUIDColumn,
)


class ReportMixin(PositionMixin):

    report_id = Column(UUIDColumn(length=16))

    created = Column(DateTime)  # the insert time of the record into the DB
    time = Column(DateTime)  # the time of observation of this data

    accuracy = Column(Integer)
    altitude = Column(Integer)
    altitude_accuracy = Column(Integer)

    # http://dev.w3.org/geo/api/spec-source.html#heading
    heading = Column(Float)

    # http://dev.w3.org/geo/api/spec-source.html#speed
    speed = Column(Float)


class ObservationMixin(BigIdMixin, ReportMixin):

    signal = Column(SmallInteger)


class CellMeasure(ObservationMixin, CellKeyPscMixin, _Model):
    __tablename__ = 'cell_measure'

    _indices = (
        Index('cell_measure_created_idx', 'created'),
        Index('cell_measure_key_idx', 'radio', 'mcc', 'mnc', 'lac', 'cid'),
    )

    asu = Column(SmallInteger)
    ta = Column(TinyInteger)


class WifiMeasure(ObservationMixin, WifiKeyMixin, _Model):
    __tablename__ = 'wifi_measure'

    _indices = (
        Index('wifi_measure_created_idx', 'created'),
        Index('wifi_measure_key_idx', 'key'),
        Index('wifi_measure_key_created_idx', 'key', 'created'),
    )

    channel = Column(SmallInteger)
    snr = Column(SmallInteger)
