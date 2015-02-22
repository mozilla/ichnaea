from datetime import datetime

import iso8601
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
    ValidationMixin,
)
from ichnaea.models.cell import (
    CellKey,
    CellKeyPscMixin,
)
from ichnaea.models.wifi import WifiKeyMixin
from ichnaea.models.sa_types import (
    TZDateTime as DateTime,
    UUIDColumn,
)
from ichnaea import util


def decode_datetime(obj):  # pragma: no cover
    if isinstance(obj, datetime):
        return obj
    try:
        return iso8601.parse_date(obj)
    except (iso8601.ParseError, TypeError):
        return util.utcnow()


class Report(PositionMixin, ValidationMixin):

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


class ObservationMixin(BigIdMixin, Report):

    @classmethod
    def create(cls, entry):
        entry = cls.validate(entry)
        if entry is None:  # pragma: no cover
            return None
        # BBB: no longer required, internaljson format decodes to datetime
        entry['time'] = decode_datetime(entry['time'])
        return cls(**entry)


class CellReport(CellKeyPscMixin, ValidationMixin):

    asu = Column(SmallInteger)
    signal = Column(SmallInteger)
    ta = Column(TinyInteger)

    @classmethod
    def valid_schema(cls):
        from ichnaea.data.schema import ValidCellReportSchema
        return ValidCellReportSchema


class CellLookup(CellReport):

    _hashkey_cls = CellKey

    @classmethod
    def valid_schema(cls):
        from ichnaea.data.schema import ValidCellLookupSchema
        return ValidCellLookupSchema


class CellObservation(ObservationMixin, CellReport, _Model):
    __tablename__ = 'cell_measure'

    _indices = (
        Index('cell_measure_created_idx', 'created'),
        Index('cell_measure_key_idx', 'radio', 'mcc', 'mnc', 'lac', 'cid'),
    )

    @classmethod
    def valid_schema(cls):
        from ichnaea.data.schema import ValidCellObservationSchema
        return ValidCellObservationSchema


class WifiReport(WifiKeyMixin, ValidationMixin):

    channel = Column(SmallInteger)
    signal = Column(SmallInteger)
    snr = Column(SmallInteger)

    @classmethod
    def valid_schema(cls):
        from ichnaea.data.schema import ValidWifiReportSchema
        return ValidWifiReportSchema


class WifiLookup(WifiReport):

    @classmethod
    def valid_schema(cls):
        from ichnaea.data.schema import ValidWifiLookupSchema
        return ValidWifiLookupSchema


class WifiObservation(ObservationMixin, WifiReport, _Model):
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
