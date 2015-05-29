import uuid

import colander
import mobile_codes
from sqlalchemy import (
    Column,
    Float,
    Index,
)
from sqlalchemy.dialects.mysql import (
    INTEGER as Integer,
    SMALLINT as SmallInteger,
)

from ichnaea import geocalc
from ichnaea.models.base import (
    _Model,
    BigIdMixin,
    CreationMixin,
    PositionMixin,
    ValidationMixin,
    ValidPositionSchema,
)
from ichnaea.models.cell import (
    CellKeyPsc,
)
from ichnaea.models import constants
from ichnaea.models.lookup import (
    CellLookup,
    ValidCellLookupSchema,
    ValidWifiLookupSchema,
    WifiLookup,
)
from ichnaea.models.schema import (
    DateTimeFromString,
    DefaultNode,
    normalized_time,
)
from ichnaea.models.sa_types import (
    TZDateTime as DateTime,
    UUIDColumn,
)


class ReportIDNode(colander.SchemaNode):
    """
    A node containing a valid report_id.
    ex: 489cc8dc9d3d11e4a87d02442b52e5a0
    """

    def preparer(self, cstruct):
        return cstruct or uuid.uuid1()


class RoundToMonthDateNode(colander.SchemaNode):
    """
    A node which takes a string date or date and
    rounds it to the first of the month.
    ex: 2015-01-01
    """

    def preparer(self, cstruct):
        return normalized_time(cstruct)


class UUIDType(colander.String):
    """
    A UUIDType will return a uuid object from either a uuid or a string.
    """

    def deserialize(self, node, cstruct):
        if not cstruct:
            return colander.null
        if isinstance(cstruct, uuid.UUID):
            return cstruct
        try:
            cstruct = uuid.UUID(hex=cstruct)
        except (AttributeError, TypeError, ValueError):
            raise colander.Invalid(node, '%r is not a valid uuid' % cstruct)
        return cstruct


class ValidReportSchema(ValidPositionSchema):
    """A schema which validates the fields present in a report."""

    accuracy = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            0, constants.MAX_ACCURACY))
    altitude = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            constants.MIN_ALTITUDE, constants.MAX_ALTITUDE))
    altitude_accuracy = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            0, constants.MAX_ALTITUDE_ACCURACY))
    heading = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            0, constants.MAX_HEADING))
    speed = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            0, constants.MAX_SPEED))
    report_id = ReportIDNode(UUIDType())
    created = colander.SchemaNode(DateTimeFromString(), missing=None)
    time = RoundToMonthDateNode(DateTimeFromString(), missing=None)


class Report(PositionMixin, ValidationMixin):

    _valid_schema = ValidReportSchema

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


class ObservationMixin(CreationMixin, BigIdMixin, Report):

    @classmethod
    def create(cls, _raise_invalid=False, **kw):
        validated = cls.validate(kw, _raise_invalid=_raise_invalid)
        if validated is None:  # pragma: no cover
            return None
        return cls(**validated)


class ValidCellReportSchema(ValidCellLookupSchema):
    """A schema which validates the cell specific fields in a report."""


class CellReport(CellLookup):

    _hashkey_cls = CellKeyPsc
    _valid_schema = ValidCellReportSchema


class ValidCellObservationSchema(ValidCellLookupSchema, ValidReportSchema):
    """A schema which validates the fields present in a cell observation."""

    def validator(self, schema, data):
        super(ValidCellObservationSchema, self).validator(schema, data)

        in_country = False
        for code in mobile_codes.mcc(str(data['mcc'])):
            in_country = in_country or geocalc.location_is_in_country(
                data['lat'], data['lon'], code.alpha2, 1)

        if not in_country:
            raise colander.Invalid(schema, (
                'Lat/lon must be inside one of '
                'the bounding boxes for the MCC'))


class CellObservation(ObservationMixin, CellReport, _Model):
    __tablename__ = 'cell_measure'

    _indices = (
        Index('cell_measure_created_idx', 'created'),
        Index('cell_measure_key_idx', 'radio', 'mcc', 'mnc', 'lac', 'cid'),
    )
    _valid_schema = ValidCellObservationSchema


class ValidWifiReportSchema(ValidWifiLookupSchema):
    """A schema which validates the wifi specific fields in a report."""


class WifiReport(WifiLookup):

    _valid_schema = ValidWifiReportSchema

    channel = Column(SmallInteger)
    signal = Column(SmallInteger)
    snr = Column(SmallInteger)


class ValidWifiObservationSchema(ValidWifiLookupSchema, ValidReportSchema):
    """A schema which validates the fields in wifi observation."""


class WifiObservation(ObservationMixin, WifiReport, _Model):
    __tablename__ = 'wifi_measure'

    _indices = (
        Index('wifi_measure_created_idx', 'created'),
        Index('wifi_measure_key_idx', 'key'),
        Index('wifi_measure_key_created_idx', 'key', 'created'),
    )
    _valid_schema = ValidWifiObservationSchema
