import base64
import struct

import colander
from enum import IntEnum
from six import string_types
from sqlalchemy import (
    BINARY,
    Boolean,
    Column,
    Index,
    PrimaryKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import (
    INTEGER as Integer,
    SMALLINT as SmallInteger,
)
from sqlalchemy.types import TypeDecorator

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

CELLAREA_STRUCT = struct.Struct('!bHHH')
"""
A compact representation of a full cell area id as a byte sequence.

Consists of a single byte for the radio type and three 16 bit unsigned
integers for the mcc, mnc and lac parts.
"""

CELLID_STRUCT = struct.Struct('!bHHHI')
"""
A compact representation of a full cell id as a byte sequence.

Consists of a single byte for the radio type, three 16 bit unsigned
integers for the mcc, mnc and lac parts and a final 32 bit unsigned
integer for the cid part.
"""


def decode_cellarea(value, codec=None):
    """
    Decode a byte sequence representing a cell area into a four-tuple
    of a Radio integer enum and three integers.

    If ``codec='base64'``, decode the value from a base64 sequence first.
    """
    if codec == 'base64':
        value = base64.b64decode(value)
    radio, mcc, mnc, lac = CELLAREA_STRUCT.unpack(value)
    return (Radio(radio), mcc, mnc, lac)


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


def encode_cellarea(radio, mcc, mnc, lac, codec=None):
    """
    Given a four-tuple of cell area parts, return a compact 7 byte
    sequence representing the cell area.

    If ``codec='base64'``, return the value as a base64 encoded sequence.
    """
    if isinstance(radio, Radio):
        radio = int(radio)
    value = CELLAREA_STRUCT.pack(radio, mcc, mnc, lac)
    if codec == 'base64':
        value = base64.b64encode(value)
    return value


def encode_cellid(radio, mcc, mnc, lac, cid, codec=None):
    """
    Given a five-tuple of cell id parts, return a compact 11 byte
    sequence representing the cell id.

    If ``codec='base64'``, return the value as a base64 encoded sequence.
    """
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


class CellAreaColumn(TypeDecorator):
    """A binary type storing Cell Area IDs."""

    impl = BINARY

    def process_bind_param(self, value, dialect):
        if value is None or isinstance(value, bytes):
            return value

        if (isinstance(value, tuple) and len(value) != 4):
            raise ValueError('Invalid Cell Area ID: %r' % value)

        radio, mcc, mnc, lac = value
        return CELLAREA_STRUCT.pack(int(radio), mcc, mnc, lac)

    def process_result_value(self, value, dialect):
        if value is None:  # pragma: no cover
            return None
        radio, mcc, mnc, lac = CELLAREA_STRUCT.unpack(value)
        return (Radio(radio), mcc, mnc, lac)


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


class CellAreaHashKey(HashKey):

    _fields = ('areaid', )


class CellIDHashKey(HashKey):

    _fields = ('cellid', )


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
            if cstruct == Radio.cdma:
                raise ValueError('Skip CDMA networks.')
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
        validator=colander.Range(constants.MIN_MCC, constants.MAX_MCC))
    mnc = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(constants.MIN_MNC, constants.MAX_MNC))
    lac = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(constants.MIN_LAC, constants.MAX_LAC))

    def validator(self, node, cstruct):
        super(ValidCellAreaKeySchema, self).validator(node, cstruct)

        if cstruct['mcc'] not in constants.ALL_VALID_MCCS:
            raise colander.Invalid(node, (
                'Check against the list of all known valid mccs'))


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

    # areaid is a derived value
    range = colander.SchemaNode(colander.Integer(), missing=0)
    avg_cell_range = colander.SchemaNode(colander.Integer(), missing=0)
    num_cells = colander.SchemaNode(colander.Integer(), missing=0)


class CellAreaMixin(CellAreaKeyMixin, TimeTrackingMixin,
                    PositionMixin, CreationMixin):

    _valid_schema = ValidCellAreaSchema()

    areaid = Column(CellAreaColumn(7), nullable=False)

    range = Column(Integer)
    avg_cell_range = Column(Integer)
    num_cells = Column(Integer(unsigned=True))

    @classmethod
    def validate(cls, entry, _raise_invalid=False, **kw):
        validated = super(CellAreaMixin, cls).validate(
            entry, _raise_invalid=_raise_invalid, **kw)
        if validated is not None and 'areaid' not in validated:
            validated['areaid'] = (
                validated['radio'],
                validated['mcc'],
                validated['mnc'],
                validated['lac'],
            )
        return validated


class ValidCellKeySchema(ValidCellAreaKeySchema):

    cid = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(constants.MIN_CID, constants.MAX_CID))
    psc = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(constants.MIN_PSC, constants.MAX_PSC))

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

        if ((cstruct.get('lac') is None or cstruct.get('cid') is None) and
                cstruct.get('psc') is None):
            raise colander.Invalid(node, ('Must have (LAC and CID) or PSC.'))

        if (cstruct['radio'] == Radio.lte and
                cstruct['psc'] is not None and
                cstruct.get('psc', 0) > constants.MAX_PSC_LTE):
            raise colander.Invalid(node, ('PSC is out of range for LTE.'))


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
        UniqueConstraint('areaid', name='cell_area_areaid_unique'),
    )


class OCIDCellArea(CellAreaMixin, _Model):
    __tablename__ = 'ocid_cell_area'

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac'),
        UniqueConstraint('areaid', name='ocid_cell_area_areaid_unique'),
    )


class CellBlocklist(CellKeyMixin, _Model):
    __tablename__ = 'cell_blacklist'

    time = Column(DateTime)
    count = Column(Integer)

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac', 'cid'),
    )
