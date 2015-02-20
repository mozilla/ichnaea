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

from ichnaea.customjson import decode_datetime
from ichnaea.models.base import (
    _Model,
    BigIdMixin,
    PositionMixin,
    ValidationMixin,
)
from ichnaea.models.cell import CellKeyPscMixin
from ichnaea.models.wifi import WifiKeyMixin
from ichnaea.models.sa_types import (
    TZDateTime as DateTime,
    UUIDColumn,
)


class ReportMixin(PositionMixin, ValidationMixin):

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

    @classmethod
    def valid_schema(cls):
        from ichnaea.data.schema import ValidReportSchema
        return ValidReportSchema


class ObservationMixin(BigIdMixin, ReportMixin):

    signal = Column(SmallInteger)

    @classmethod
    def create(cls, entry):
        entry = cls.validate(entry)
        if entry is None:  # pragma: no cover
            return None
        # BBB: no longer required, internaljson format decodes to datetime
        entry['time'] = decode_datetime(entry['time'])
        return cls(**entry)


class CellObservation(ObservationMixin, CellKeyPscMixin, _Model):
    __tablename__ = 'cell_measure'

    _indices = (
        Index('cell_measure_created_idx', 'created'),
        Index('cell_measure_key_idx', 'radio', 'mcc', 'mnc', 'lac', 'cid'),
    )

    @classmethod
    def valid_schema(cls):
        from ichnaea.data.schema import ValidCellObservationSchema
        return ValidCellObservationSchema

    asu = Column(SmallInteger)
    ta = Column(TinyInteger)


class WifiObservation(ObservationMixin, WifiKeyMixin, _Model):
    __tablename__ = 'wifi_measure'

    _indices = (
        Index('wifi_measure_created_idx', 'created'),
        Index('wifi_measure_key_idx', 'key'),
        Index('wifi_measure_key_created_idx', 'key', 'created'),
    )

    @classmethod
    def valid_schema(cls):
        from ichnaea.data.schema import ValidWifiObservationSchema
        return ValidWifiObservationSchema

    channel = Column(SmallInteger)
    snr = Column(SmallInteger)
