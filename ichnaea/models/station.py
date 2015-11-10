from enum import IntEnum
import math

import colander
from six import string_types
from sqlalchemy import Column
from sqlalchemy.dialects.mysql import (
    DOUBLE as Double,
)

from ichnaea.models import constants
from ichnaea.models.sa_types import TZDateTime as DateTime
from ichnaea.models.schema import (
    DateTimeFromString,
    DefaultNode,
    ValidatorNode,
)


class StationSource(IntEnum):
    """
    The :term:`station` source states on what kind of data the
    :term:`station` record is based on. A lower integer value hints at
    a better quality of the observation data that went into this
    :term:`station` record.
    """

    fixed = 0  #: Outside knowledge about the true position of the station.
    gnss = 3  #: Global navigation satellite system based data.
    fused = 6  #: Observation data positioned based on fused data.
    query = 9  #: Position estimate based on query data.


class StationSourceNode(DefaultNode):
    """A node containing a valid station source."""

    def validator(self, node, cstruct):
        super(StationSourceNode, self).validator(node, cstruct)

        if type(cstruct) is StationSource:
            return True

        raise colander.Invalid(  # pragma: no cover
            node, 'Invalid station source')


class StationSourceType(colander.Integer):
    """
    A StationSourceType will return a StationSource IntEnum object.
    """

    def deserialize(self, node, cstruct):  # pragma: no cover
        if cstruct is colander.null:
            return None
        if isinstance(cstruct, StationSource):
            return cstruct
        try:
            if isinstance(cstruct, string_types):
                cstruct = StationSource[cstruct]
            else:
                cstruct = StationSource(cstruct)
        except (KeyError, ValueError):
            raise colander.Invalid(node, (
                '%r is not a valid station source' % cstruct))
        return cstruct


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
    """A database model mixin with lat and lon float fields."""

    lat = Column(Double(asdecimal=False))
    lon = Column(Double(asdecimal=False))


class ValidTimeTrackingSchema(colander.MappingSchema, ValidatorNode):
    """A schema which validates the fields used for time tracking."""

    created = colander.SchemaNode(DateTimeFromString(), missing=None)
    modified = colander.SchemaNode(DateTimeFromString(), missing=None)


class TimeTrackingMixin(object):
    """A database model mixin with created and modified datetime fields."""

    created = Column(DateTime)
    modified = Column(DateTime)


class ScoreMixin(object):
    """A database model mixin exposing a score."""

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

    def score(self, now):
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
        collected_over = max((self.modified - self.created).days, 1)
        collection_weight = min(collected_over / 10.0, 1.0)

        return age_weight * collection_weight * self.score_sample_weight()
