import base64
import struct

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
from ichnaea.models.sa_types import (
    TinyIntEnum,
    TZDateTime as DateTime,
)
from ichnaea.models.schema import (
    CopyingSchema,
    DefaultNode,
    FieldSchema,
)
from ichnaea.models.station import (
    BboxMixin,
    ValidBboxSchema,
)

CELLID_STRUCT = struct.Struct('!bHHHI')
"""
A compact representation of a full cell id as a byte sequence.

Consists of a single byte for the radio type, three 16 bit unsigned
integers for the mcc, mnc and lac parts and a final 32 bit unsigned
integer for the cid part.
"""


def decode_cellid(value, codec=None):
    """
    Decode a byte sequence representing a cell id into a five-tuple
    of a Radio integer enum and four integers.

    If ``codec='base64'``, decode the value from a base64 sequence first.
    """
    if codec == 'base64':
        value = base64.b64decode(value)
    radio, mcc, mnc, lac, cid = CELLID_STRUCT.unpack(value)
    return (Radio(radio), mcc, mnc, lac, cid)


def encode_cellid(radio, mcc, mnc, lac, cid, codec=None):
    """
    Given a five-tuple of cell id parts, return a compact 11 byte
    sequence representing the cell id.

    If the radio type is given as CDMA, clobbers the mcc value and
    uses 0 instead, as the mcc is not part of the unique cell id key
    for CDMA radio networks.

    If ``codec='base64'``, return the value as a base64 encoded sequence.
    """
    if radio == Radio.cdma:
        mcc = 0
    if isinstance(radio, Radio):
        radio = int(radio)
    value = CELLID_STRUCT.pack(radio, mcc, mnc, lac, cid)
    if codec == 'base64':
        value = base64.b64encode(value)
    return value


class Radio(IntEnum):
    __order__ = 'gsm cdma wcdma umts lte'

    gsm = 0
    cdma = 1
    wcdma = 2
    umts = 2
    lte = 3

    @classmethod
    def _gsm_family(cls):
        return GSM_FAMILY

GSM_FAMILY = (Radio.gsm, Radio.wcdma, Radio.lte)


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
    """A node containing a valid radio enum."""

    def validator(self, node, cstruct):
        super(RadioNode, self).validator(node, cstruct)

        if type(cstruct) is Radio:
            return True

        raise colander.Invalid(node, 'Invalid radio type')  # pragma: no cover


class RadioType(colander.Integer):
    """A RadioType will return a Radio IntEnum object."""

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
    """A RadioType will return a Radio IntEnum as a string."""

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

        if (cstruct['radio'] in GSM_FAMILY and
                cstruct['mnc'] is not None and
                cstruct.get('mnc', 0) > 999):
            raise colander.Invalid(node, (
                'Skip GSM/LTE/UMTS towers with an invalid MNC'))

        if (cstruct['radio'] in GSM_FAMILY and
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

    range = colander.SchemaNode(colander.Integer(), missing=0)
    avg_cell_range = colander.SchemaNode(colander.Integer(), missing=0)
    num_cells = colander.SchemaNode(colander.Integer(), missing=0)


class CellAreaMixin(CellAreaKeyMixin, TimeTrackingMixin,
                    PositionMixin, CreationMixin):

    _valid_schema = ValidCellAreaSchema()

    range = Column(Integer)
    avg_cell_range = Column(Integer)
    num_cells = Column(Integer(unsigned=True))


class ValidCellKeySchema(ValidCellAreaKeySchema):

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


class ValidBaseStationSchema(ValidPositionSchema, ValidTimeTrackingSchema):

    range = colander.SchemaNode(colander.Integer(), missing=0)
    total_measures = colander.SchemaNode(colander.Integer(), missing=0)


class BaseStationMixin(PositionMixin, TimeTrackingMixin):

    range = Column(Integer)
    total_measures = Column(Integer(unsigned=True))


class ValidCellSchema(ValidCellKeySchema,
                      ValidBaseStationSchema, ValidBboxSchema):
    """A schema which validates the fields in a cell."""


class Cell(CellMixin, BaseStationMixin, BboxMixin, CreationMixin, _Model):
    __tablename__ = 'cell'

    new_measures = Column(Integer(unsigned=True))

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac', 'cid'),
        Index('cell_created_idx', 'created'),
        Index('cell_modified_idx', 'modified'),
    )
    _valid_schema = ValidCellSchema()


class ValidOCIDCellSchema(ValidCellKeySchema, ValidBaseStationSchema):
    """A schema which validates the fields present in a :term:`OCID` cell."""

    changeable = colander.SchemaNode(colander.Boolean(), missing=True)


class OCIDCell(CellMixin, BaseStationMixin, CreationMixin, _Model):
    __tablename__ = 'ocid_cell'

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac', 'cid'),
        Index('ocid_cell_created_idx', 'created'),
    )
    _valid_schema = ValidOCIDCellSchema()

    changeable = Column(Boolean)

    @property
    def min_lat(self):
        return geocalc.latitude_add(self.lat, self.lon, -self.range)

    @property
    def max_lat(self):
        return geocalc.latitude_add(self.lat, self.lon, self.range)

    @property
    def min_lon(self):
        return geocalc.longitude_add(self.lat, self.lon, -self.range)

    @property
    def max_lon(self):
        return geocalc.longitude_add(self.lat, self.lon, self.range)


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


class CellBlocklist(CellKeyMixin, _Model):
    __tablename__ = 'cell_blacklist'

    time = Column(DateTime)
    count = Column(Integer)

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac', 'cid'),
    )
