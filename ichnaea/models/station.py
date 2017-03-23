import colander
from sqlalchemy import (
    Column,
    Date,
    String,
)
from sqlalchemy.dialects.mysql import (
    DOUBLE as Double,
    INTEGER as Integer,
    TINYINT as TinyInteger,
)

from ichnaea.models.base import CreationMixin
from ichnaea.models import constants
from ichnaea.models.constants import TEMPORARY_BLOCKLIST_DURATION
from ichnaea.models.sa_types import (
    TinyIntEnum,
    TZDateTime as DateTime,
)
from ichnaea.models.schema import (
    DateFromString,
    DateTimeFromString,
    ReportSourceNode,
    ReportSourceType,
    ValidatorNode,
)
from ichnaea import util


class ValidBboxSchema(colander.MappingSchema, ValidatorNode):
    """A schema which validates fields present in a bounding box."""

    max_lat = colander.SchemaNode(
        colander.Float(),
        missing=None,
        validator=colander.Range(constants.MIN_LAT, constants.MAX_LAT))
    min_lat = colander.SchemaNode(
        colander.Float(),
        missing=None,
        validator=colander.Range(constants.MIN_LAT, constants.MAX_LAT))

    max_lon = colander.SchemaNode(
        colander.Float(),
        missing=None,
        validator=colander.Range(constants.MIN_LON, constants.MAX_LON))
    min_lon = colander.SchemaNode(
        colander.Float(),
        missing=None,
        validator=colander.Range(constants.MIN_LON, constants.MAX_LON))


class BboxMixin(object):
    """A model mix-in with columns for a bounding box."""

    max_lat = Column(Double(asdecimal=False))
    min_lat = Column(Double(asdecimal=False))

    max_lon = Column(Double(asdecimal=False))
    min_lon = Column(Double(asdecimal=False))


class ValidPositionSchema(colander.MappingSchema, ValidatorNode):
    """A schema which validates the fields present in a position."""

    lat = colander.SchemaNode(
        colander.Float(),
        missing=None,
        validator=colander.Range(constants.MIN_LAT, constants.MAX_LAT))
    lon = colander.SchemaNode(
        colander.Float(),
        missing=None,
        validator=colander.Range(constants.MIN_LON, constants.MAX_LON))


class PositionMixin(object):
    """A model mix-in with lat and lon float columns."""

    lat = Column(Double(asdecimal=False))
    lon = Column(Double(asdecimal=False))


class ValidTimeTrackingSchema(colander.MappingSchema, ValidatorNode):
    """A schema which validates the fields used for time tracking."""

    created = colander.SchemaNode(DateTimeFromString(), missing=None)
    modified = colander.SchemaNode(DateTimeFromString(), missing=None)


class TimeTrackingMixin(object):
    """A model mix-in with created and modified datetime columns."""

    created = Column(DateTime)
    modified = Column(DateTime)


class ValidStationSchema(ValidBboxSchema,
                         ValidPositionSchema,
                         ValidTimeTrackingSchema):
    """A schema which validates the fields in a station."""

    radius = colander.SchemaNode(colander.Integer(), missing=None)
    region = colander.SchemaNode(colander.String(), missing=None)
    samples = colander.SchemaNode(colander.Integer(), missing=None)
    source = ReportSourceNode(ReportSourceType(), missing=None)
    weight = colander.SchemaNode(colander.Float(), missing=None)

    last_seen = colander.SchemaNode(DateFromString(), missing=None)
    block_first = colander.SchemaNode(DateFromString(), missing=None)
    block_last = colander.SchemaNode(DateFromString(), missing=None)
    block_count = colander.SchemaNode(colander.Integer(), missing=None)


class StationMixin(BboxMixin,
                   PositionMixin,
                   TimeTrackingMixin,
                   CreationMixin):
    """A model mix-in with common station columns."""

    radius = Column(Integer(unsigned=True))
    region = Column(String(2))
    samples = Column(Integer(unsigned=True))
    source = Column(TinyIntEnum(constants.ReportSource))
    weight = Column(Double(asdecimal=False))

    last_seen = Column(Date)
    block_first = Column(Date)
    block_last = Column(Date)
    block_count = Column(TinyInteger(unsigned=True))


def station_blocked(obj, today=None):
    """Is the station currently blocked?"""
    if today is None:
        today = util.utcnow().date()

    if obj.block_last:
        # Block the station if it has been at most X days since
        # the last time it has been blocked.
        age = today - obj.block_last
        if bool(age < TEMPORARY_BLOCKLIST_DURATION):
            return True

    if (obj.created and obj.block_count):
        # Allow the station to be blocked once for each 30 day
        # period of the time it has been known to us.
        age = abs((obj.created.date() - today).days)
        if obj.block_count >= int(round(age / 30.0)):
            return True

    return False
