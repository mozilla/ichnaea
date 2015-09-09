import colander
from enum import IntEnum
from six import string_types
from sqlalchemy import Column
from sqlalchemy.dialects.mysql import (
    DOUBLE as Double,
)

from ichnaea.models import constants
from ichnaea.models.schema import (
    CopyingSchema,
    DefaultNode,
    FieldSchema,
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


class ValidBboxSchema(FieldSchema, CopyingSchema):
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
