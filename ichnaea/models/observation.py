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
    CreationMixin,
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
        from ichnaea.models.schema import ValidReportSchema
        return ValidReportSchema


class ObservationMixin(CreationMixin, BigIdMixin, Report):

    @classmethod
    def create(cls, _raise_invalid=False, **kw):
        validated = cls.validate(kw, _raise_invalid=_raise_invalid)
        if validated is None:  # pragma: no cover
            return None
        # BBB: no longer required, internaljson format decodes to datetime
        validated['time'] = decode_datetime(validated['time'])
        return cls(**validated)


class CellReport(CellKeyPscMixin, ValidationMixin):

    asu = Column(SmallInteger)
    signal = Column(SmallInteger)
    ta = Column(TinyInteger)

    @classmethod
    def valid_schema(cls):
        from ichnaea.models.schema import ValidCellReportSchema
        return ValidCellReportSchema


class CellLookup(CellReport):

    _hashkey_cls = CellKey

    @classmethod
    def valid_schema(cls):
        from ichnaea.models.schema import ValidCellLookupSchema
        return ValidCellLookupSchema


class CellObservation(ObservationMixin, CellReport, _Model):
    __tablename__ = 'cell_measure'

    _indices = (
        Index('cell_measure_created_idx', 'created'),
        Index('cell_measure_key_idx', 'radio', 'mcc', 'mnc', 'lac', 'cid'),
    )

    @classmethod
    def valid_schema(cls):
        from ichnaea.models.schema import ValidCellObservationSchema
        return ValidCellObservationSchema


class WifiReport(WifiKeyMixin, ValidationMixin):

    channel = Column(SmallInteger)
    signal = Column(SmallInteger)
    snr = Column(SmallInteger)

    @classmethod
    def valid_schema(cls):
        from ichnaea.models.schema import ValidWifiReportSchema
        return ValidWifiReportSchema


class WifiLookup(WifiReport):

    @classmethod
    def valid_schema(cls):
        from ichnaea.models.schema import ValidWifiLookupSchema
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
        from ichnaea.models.schema import ValidWifiObservationSchema
        return ValidWifiObservationSchema
