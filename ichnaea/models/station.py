import math

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

from ichnaea.constants import (
    PERMANENT_BLOCKLIST_THRESHOLD,
    TEMPORARY_BLOCKLIST_DURATION,
)
from ichnaea.models.base import CreationMixin
from ichnaea.models import constants
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

    max_lat = Column(Double(asdecimal=False))  #:
    min_lat = Column(Double(asdecimal=False))  #:

    max_lon = Column(Double(asdecimal=False))  #:
    min_lon = Column(Double(asdecimal=False))  #:


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

    lat = Column(Double(asdecimal=False))  #:
    lon = Column(Double(asdecimal=False))  #:


class ValidTimeTrackingSchema(colander.MappingSchema, ValidatorNode):
    """A schema which validates the fields used for time tracking."""

    created = colander.SchemaNode(DateTimeFromString(), missing=None)
    modified = colander.SchemaNode(DateTimeFromString(), missing=None)


class TimeTrackingMixin(object):
    """A model mix-in with created and modified datetime columns."""

    created = Column(DateTime)  #:
    modified = Column(DateTime)  #:


class ScoreMixin(object):
    """A model mix-in exposing a score."""

    def score_sample_weight(self):
        # treat networks for which we get the exact same
        # observations multiple times as if we only got 1 sample
        samples = self.samples
        if samples > 1 and not self.radius:
            samples = 1

        # sample_weight is a number between:
        # 0.5 for 1 sample
        # 1.0 for 2 samples
        # 3.32 for 10 samples
        # 6.64 for 100 samples
        # 10.0 for 1024 samples or more
        return min(max(math.log(max(samples, 1), 2), 0.5), 10.0)

    def score_created_position(self):
        # The creation date stays intact after a station moved to a new
        # position. For scoring purposes we only want to consider how
        # long the station has been at its current position.
        created = self.created.date()
        if not self.block_last:
            return created
        return max(created, self.block_last)

    def score(self, now):
        """
        Returns a score as a floating point number.

        The score represents the quality or trustworthiness of this record.

        :param now: The current time.
        :type now: datetime.datetime
        """
        # age_weight is a number between:
        # 1.0 (data from last month) to
        # 0.277 (data from a year ago)
        # 0.2 (data from two years ago)
        month_old = max((now - self.modified).days, 0) // 30
        age_weight = 1 / math.sqrt(month_old + 1)

        # collection_weight is a number between:
        # 0.1 (data was only seen on a single day)
        # 0.2 (data was seen on two different days)
        # 1.0 (data was first and last seen at least 10 days apart)
        last_seen = self.modified.date()
        if self.last_seen is not None:
            last_seen = max(last_seen, self.last_seen)

        collected_over = max(
            (last_seen - self.score_created_position()).days, 1)
        collection_weight = min(collected_over / 10.0, 1.0)

        return age_weight * collection_weight * self.score_sample_weight()


class ValidStationSchema(ValidBboxSchema,
                         ValidPositionSchema,
                         ValidTimeTrackingSchema):
    """A schema which validates the fields in a station."""

    radius = colander.SchemaNode(colander.Integer(), missing=0)
    region = colander.SchemaNode(colander.String(), missing=None)
    samples = colander.SchemaNode(colander.Integer(), missing=0)
    source = ReportSourceNode(ReportSourceType(), missing=None)
    weight = colander.SchemaNode(colander.Float(), missing=None)

    last_seen = colander.SchemaNode(DateFromString(), missing=None)
    block_first = colander.SchemaNode(DateFromString(), missing=None)
    block_last = colander.SchemaNode(DateFromString(), missing=None)
    block_count = colander.SchemaNode(colander.Integer(), missing=0)


class StationMixin(BboxMixin,
                   PositionMixin,
                   TimeTrackingMixin,
                   CreationMixin,
                   ScoreMixin):
    """A model mix-in with common station columns."""

    radius = Column(Integer(unsigned=True))  #:
    region = Column(String(2))  #:
    samples = Column(Integer(unsigned=True))  #:
    source = Column(TinyIntEnum(constants.ReportSource))  #:
    weight = Column(Double(asdecimal=False))  #:

    last_seen = Column(Date)  #:
    block_first = Column(Date)  #:
    block_last = Column(Date)  #:
    block_count = Column(TinyInteger(unsigned=True))  #:

    def blocked(self, today=None):
        """Is the station currently blocked?"""
        if (self.block_count and
                self.block_count >= PERMANENT_BLOCKLIST_THRESHOLD):
            return True

        temporary = False
        if self.block_last:
            if today is None:
                today = util.utcnow().date()
            age = today - self.block_last
            temporary = age < TEMPORARY_BLOCKLIST_DURATION

        return bool(temporary)
