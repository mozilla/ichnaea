import colander
from enum import IntEnum
from six import string_types
from sqlalchemy import (
    Column,
    Index,
    Boolean,
    PrimaryKeyConstraint,
)
from sqlalchemy.dialects.mysql import (
    INTEGER as Integer,
    SMALLINT as SmallInteger,
)

from ichnaea import geocalc
from ichnaea.models.base import (
    _Model,
    CreationMixin,
    PositionMixin,
    TimeTrackingMixin,
    ValidPositionSchema,
    ValidTimeTrackingSchema,
)
from ichnaea.models import constants
from ichnaea.models.hashkey import (
    HashKey,
    HashKeyQueryMixin,
)
from ichnaea.models.sa_types import TinyIntEnum
from ichnaea.models.schema import (
    CopyingSchema,
    DefaultNode,
    FieldSchema,
)
from ichnaea.models.station import (
    BaseStationMixin,
    StationMixin,
    ValidBaseStationSchema,
    StationBlacklistMixin,
    ValidStationSchema,
)


class Radio(IntEnum):
    __order__ = 'gsm cdma wcdma umts lte'

    gsm = 0
    cdma = 1
    wcdma = 2
    umts = 2
    lte = 3

    @classmethod
    def _gsm_family(cls):
        return (cls.gsm, cls.wcdma, cls.lte)


def encode_radio_dict(dct):
    if 'radio' in dct and type(dct['radio']) == Radio:
        dct['radio'] = int(dct['radio'])
    return dct


def decode_radio_dict(dct):
    if 'radio' in dct and dct['radio'] is not None and \
       not type(dct['radio']) == Radio:
        dct['radio'] = Radio(dct['radio'])
    return dct


class CellHashKey(HashKey):

    @classmethod
    def _from_json_value(cls, value):
        data = value.copy()
        data['radio'] = Radio(data['radio'])
        return cls(**data)

    def _to_json_value(self):
        value = self.__dict__.copy()
        value['radio'] = int(value['radio'])
        return value


class RadioNode(DefaultNode):
    """
    A node containing a valid radio enum.
    """

    def validator(self, node, cstruct):
        super(RadioNode, self).validator(node, cstruct)

        if type(cstruct) is Radio:
            return True

        raise colander.Invalid(node, 'Invalid radio type')  # pragma: no cover


class RadioType(colander.Integer):
    """
    A RadioType will return a Radio IntEnum object.
    """

    def deserialize(self, node, cstruct):
        if cstruct is colander.null:  # pragma: no cover
            return None
        if isinstance(cstruct, Radio):
            return cstruct
        try:
            if isinstance(cstruct, string_types):
                cstruct = Radio[cstruct]
            else:  # pragma: no cover
                cstruct = Radio(cstruct)
        except (KeyError, ValueError):
            raise colander.Invalid(node, (
                '%r is not a valid radio type' % cstruct))
        return cstruct


class RadioStringType(colander.String):
    """
    A RadioType will return a Radio IntEnum as a string.
    """

    def deserialize(self, node, cstruct):
        if isinstance(cstruct, Radio):
            return cstruct.name

        raise colander.Invalid(  # pragma: no cover
            node, ('%r is not a valid radio type' % cstruct))


class CellAreaKey(CellHashKey):

    _fields = ('radio', 'mcc', 'mnc', 'lac')


class CellKey(CellHashKey):

    _fields = ('radio', 'mcc', 'mnc', 'lac', 'cid')


class CellKeyPsc(CellHashKey):

    _fields = ('radio', 'mcc', 'mnc', 'lac', 'cid', 'psc')


class ValidCellAreaKeySchema(FieldSchema, CopyingSchema):
    """A schema which validates the fields present in a cell area key."""

    radio = RadioNode(RadioType())
    mcc = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(1, 999))
    mnc = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(0, 32767))
    lac = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(
            constants.MIN_LAC, constants.MAX_LAC_ALL))

    def validator(self, node, cstruct):
        super(ValidCellAreaKeySchema, self).validator(node, cstruct)

        if cstruct['mcc'] not in constants.ALL_VALID_MCCS:
            raise colander.Invalid(node, (
                'Check against the list of all known valid mccs'))

        if (cstruct['radio'] in Radio._gsm_family() and
                cstruct['mnc'] is not None and
                cstruct.get('mnc', 0) > 999):
            raise colander.Invalid(node, (
                'Skip GSM/LTE/UMTS towers with an invalid MNC'))

        if (cstruct['radio'] in Radio._gsm_family() and
                cstruct['lac'] is not None and
                cstruct.get('lac', 0) > constants.MAX_LAC_GSM_UMTS_LTE):
            raise colander.Invalid(node, (
                'LAC is out of range for GSM/UMTS/LTE.'))


class CellAreaKeyMixin(HashKeyQueryMixin):

    _hashkey_cls = CellAreaKey
    _query_batch = 25

    radio = Column(TinyIntEnum(Radio), autoincrement=False, default=None)
    mcc = Column(SmallInteger, autoincrement=False, default=None)
    mnc = Column(SmallInteger, autoincrement=False, default=None)
    lac = Column(SmallInteger(unsigned=True),
                 autoincrement=False, default=None)


class ValidCellAreaSchema(ValidCellAreaKeySchema,
                          ValidPositionSchema,
                          ValidTimeTrackingSchema):
    """A schema which validates the fields present in a cell area."""

    range = colander.SchemaNode(colander.Integer(), missing=0)
    avg_cell_range = colander.SchemaNode(colander.Integer(), missing=0)
    num_cells = colander.SchemaNode(colander.Integer(), missing=0)


class CellAreaMixin(CellAreaKeyMixin, TimeTrackingMixin,
                    PositionMixin, CreationMixin):

    _valid_schema = ValidCellAreaSchema

    range = Column(Integer)
    avg_cell_range = Column(Integer)
    num_cells = Column(Integer(unsigned=True))


class ValidCellKeySchema(ValidCellAreaKeySchema):
    """A schema which validates the fields present in a cell key."""

    cid = DefaultNode(
        colander.Integer(),
        missing=None, validator=colander.Range(
            constants.MIN_CID, constants.MAX_CID_ALL))
    psc = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(0, 512))

    def deserialize(self, data):
        if data:
            # deserialize and validate radio field early
            radio_node = self.fields['radio']
            radio = radio_node.deserialize(data.get('radio', colander.null))
            if radio_node.validator(radio_node, radio):
                data['radio'] = radio

            # If the cell id > 65535 then it must be a WCDMA tower
            if (data['radio'] == Radio.gsm and
                    data.get('cid') is not None and
                    data.get('cid', 0) > constants.MAX_CID_GSM):
                data['radio'] = Radio.wcdma

            # Treat cid=65535 without a valid lac as an unspecified value
            if (data.get('lac') is None and
                    data.get('cid') == constants.MAX_CID_GSM):
                data['cid'] = None

        return super(ValidCellKeySchema, self).deserialize(data)

    def validator(self, node, cstruct):
        super(ValidCellKeySchema, self).validator(node, cstruct)

        lac_missing = cstruct.get('lac') is None
        cid_missing = cstruct.get('cid') is None
        psc_missing = cstruct.get('psc') is None

        if cstruct['radio'] == Radio.cdma and (lac_missing or cid_missing):
            raise colander.Invalid(node, (
                'Skip CDMA towers missing lac or cid '
                '(no psc on CDMA exists to backfill using inference)'))

        if (lac_missing or cid_missing) and psc_missing:
            raise colander.Invalid(node, (
                'Must have (lac and cid) or '
                'psc (psc-only to use in backfill)'))

        if (cstruct['radio'] == Radio.cdma and
                cstruct['cid'] is not None and
                cstruct.get('cid', 0) > constants.MAX_CID_CDMA):
            raise colander.Invalid(node, (
                'CID is out of range for CDMA.'))

        if (cstruct['radio'] == Radio.lte and
                cstruct['cid'] is not None and
                cstruct.get('cid', 0) > constants.MAX_CID_LTE):
            raise colander.Invalid(node, (
                'CID is out of range for LTE.'))


class CellKeyMixin(CellAreaKeyMixin):

    _hashkey_cls = CellKey
    _query_batch = 20

    cid = Column(Integer(unsigned=True), autoincrement=False, default=None)


class ValidCellSignalSchema(FieldSchema, CopyingSchema):
    """
    A schema which validates the fields related to cell signal
    strength and quality.
    """

    asu = DefaultNode(
        colander.Integer(),
        missing=None, validator=colander.Range(0, 97))
    signal = DefaultNode(
        colander.Integer(),
        missing=None, validator=colander.Range(-150, -1))
    ta = DefaultNode(
        colander.Integer(),
        missing=None, validator=colander.Range(0, 63))

    def deserialize(self, data):
        if data:
            # Sometimes the asu and signal fields are swapped
            if (data.get('asu') is not None and
                    data.get('asu', 0) < -1 and
                    data.get('signal', None) == 0):
                data['signal'] = data['asu']
                data['asu'] = None
        return super(ValidCellSignalSchema, self).deserialize(data)


class CellMixin(CellKeyMixin):

    psc = Column(SmallInteger, autoincrement=False)


class ValidCellSchema(ValidCellKeySchema, ValidStationSchema):
    """A schema which validates the fields in cell."""


class Cell(CellMixin, StationMixin, CreationMixin, _Model):
    __tablename__ = 'cell'

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac', 'cid'),
        Index('cell_created_idx', 'created'),
        Index('cell_modified_idx', 'modified'),
    )
    _valid_schema = ValidCellSchema


class ValidOCIDCellSchema(ValidCellKeySchema, ValidBaseStationSchema):
    """A schema which validates the fields present in a OCID cell."""

    changeable = colander.SchemaNode(colander.Boolean(), missing=True)


class OCIDCell(CellMixin, BaseStationMixin, CreationMixin, _Model):
    __tablename__ = 'ocid_cell'

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac', 'cid'),
        Index('ocid_cell_created_idx', 'created'),
    )
    _valid_schema = ValidOCIDCellSchema

    changeable = Column(Boolean)

    @property
    def min_lat(self):
        return geocalc.add_meters_to_latitude(self.lat, -self.range)

    @property
    def max_lat(self):
        return geocalc.add_meters_to_latitude(self.lat, self.range)

    @property
    def min_lon(self):
        return geocalc.add_meters_to_longitude(self.lat, self.lon, -self.range)

    @property
    def max_lon(self):
        return geocalc.add_meters_to_longitude(self.lat, self.lon, self.range)


class CellArea(CellAreaMixin, _Model):
    __tablename__ = 'cell_area'

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac'),
    )


class OCIDCellArea(CellAreaMixin, _Model):
    __tablename__ = 'ocid_cell_area'

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac'),
    )


class CellBlacklist(CellKeyMixin, StationBlacklistMixin, _Model):
    __tablename__ = 'cell_blacklist'

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac', 'cid'),
    )
