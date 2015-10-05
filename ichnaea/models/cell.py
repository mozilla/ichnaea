import base64
import struct

import colander
from enum import IntEnum
from sqlalchemy import (
    BINARY,
    Boolean,
    Column,
    Date,
    Index,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import (
    INTEGER as Integer,
    SMALLINT as SmallInteger,
    TINYINT as TinyInteger,
)
from sqlalchemy.types import TypeDecorator

from ichnaea.models.base import (
    _Model,
    CreationMixin,
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
    DateFromString,
    DefaultNode,
    ValidatorNode,
)
from ichnaea.models.station import (
    BboxMixin,
    PositionMixin,
    StationSource,
    StationSourceNode,
    StationSourceType,
    TimeTrackingMixin,
    ValidBboxSchema,
    ValidPositionSchema,
    ValidTimeTrackingSchema,
)
from ichnaea.region import GEOCODER


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


class Radio(IntEnum):
    __order__ = 'gsm cdma wcdma umts lte'

    gsm = 0
    cdma = 1
    wcdma = 2
    umts = 2
    lte = 3


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


class CellIdColumn(TypeDecorator):
    """A binary type storing Cell IDs."""

    impl = BINARY

    def process_bind_param(self, value, dialect):
        if value is None or isinstance(value, bytes):
            return value

        if (isinstance(value, tuple) and len(value) != 5):
            raise ValueError('Invalid Cell ID: %r' % value)

        radio, mcc, mnc, lac, cid = value
        return CELLID_STRUCT.pack(int(radio), mcc, mnc, lac, cid)

    def process_result_value(self, value, dialect):
        if value is None:  # pragma: no cover
            return None
        radio, mcc, mnc, lac, cid = CELLID_STRUCT.unpack(value)
        return (Radio(radio), mcc, mnc, lac, cid)


class RadioType(colander.Integer):
    """A RadioType will return a Radio IntEnum object."""

    def deserialize(self, node, cstruct):
        if ((isinstance(cstruct, Radio) and cstruct is not Radio['cdma']) or
                cstruct is colander.null):
            return cstruct
        error = False
        try:
            cstruct = Radio[cstruct]
            if cstruct is Radio['cdma']:
                error = True
        except KeyError:
            error = True
        if error:
            raise colander.Invalid(node, (
                '%r is not a valid radio type' % cstruct))
        return cstruct


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


class CellKey(CellHashKey):

    _fields = ('radio', 'mcc', 'mnc', 'lac', 'cid')


class ValidCellAreaKeySchema(colander.MappingSchema, ValidatorNode):

    radio = DefaultNode(RadioType())
    mcc = colander.SchemaNode(colander.Integer())
    mnc = colander.SchemaNode(colander.Integer())
    lac = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(constants.MIN_LAC, constants.MAX_LAC))

    def validator(self, node, cstruct):
        super(ValidCellAreaKeySchema, self).validator(node, cstruct)

        if cstruct['mcc'] not in constants.ALL_VALID_MCCS:
            raise colander.Invalid(node, (
                'Check against the list of all known valid mccs'))

        if not (constants.MIN_MNC <= cstruct['mnc'] <= constants.MAX_MNC):
            raise colander.Invalid(node, ('MNC out of valid range.'))


class ValidCellKeySchema(ValidCellAreaKeySchema):

    cid = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(constants.MIN_CID, constants.MAX_CID))
    psc = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(constants.MIN_PSC, constants.MAX_PSC))

    def __init__(self, *args, **kw):
        super(ValidCellKeySchema, self).__init__(*args, **kw)
        self.radio_node = self.get('radio')

    def deserialize(self, data):
        if data:
            # shallow copy
            data = dict(data)
            # deserialize and validate radio field early
            data['radio'] = self.radio_node.deserialize(
                data.get('radio', colander.null))

            # If the cell id > 65535 then it must be a WCDMA tower
            if (data['radio'] is Radio['gsm'] and
                    data.get('cid') is not None and
                    data.get('cid', 0) > constants.MAX_CID_GSM):
                data['radio'] = Radio['wcdma']

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

        if (cstruct['radio'] is Radio['lte'] and
                cstruct.get('psc') is not None and
                cstruct.get('psc', 0) > constants.MAX_PSC_LTE):
            raise colander.Invalid(node, ('PSC is out of range for LTE.'))


class ValidCellSignalSchema(colander.MappingSchema, ValidatorNode):
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
                # shallow copy
                data = dict(data)
                data['signal'] = data['asu']
                data['asu'] = None
        return super(ValidCellSignalSchema, self).deserialize(data)


class ValidCellAreaSchema(ValidCellAreaKeySchema,
                          ValidPositionSchema,
                          ValidTimeTrackingSchema):

    # areaid is a derived value
    range = colander.SchemaNode(colander.Integer(), missing=0)
    avg_cell_range = colander.SchemaNode(colander.Integer(), missing=0)
    num_cells = colander.SchemaNode(colander.Integer(), missing=0)


class CellArea(PositionMixin, TimeTrackingMixin, CreationMixin, _Model):
    __tablename__ = 'cell_area'

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac'),
        UniqueConstraint('areaid', name='cell_area_areaid_unique'),
    )
    _valid_schema = ValidCellAreaSchema()

    radio = Column(TinyIntEnum(Radio), autoincrement=False, default=None)
    mcc = Column(SmallInteger, autoincrement=False, default=None)
    mnc = Column(SmallInteger, autoincrement=False, default=None)
    lac = Column(SmallInteger(unsigned=True),
                 autoincrement=False, default=None)

    areaid = Column(CellAreaColumn(7), nullable=False)
    range = Column(Integer)
    avg_cell_range = Column(Integer)
    num_cells = Column(Integer(unsigned=True))

    @classmethod
    def validate(cls, entry, _raise_invalid=False, **kw):
        validated = super(CellArea, cls).validate(
            entry, _raise_invalid=_raise_invalid, **kw)
        if validated is not None and 'areaid' not in validated:
            validated['areaid'] = (
                validated['radio'],
                validated['mcc'],
                validated['mnc'],
                validated['lac'],
            )
        return validated

    @property
    def radius(self):
        # BBB: alias
        return self.range

    @property
    def avg_cell_radius(self):
        # BBB: alias
        return self.avg_cell_range


class OCIDCellArea(PositionMixin, TimeTrackingMixin, CreationMixin, _Model):
    # BBB
    __tablename__ = 'ocid_cell_area'

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac'),
        UniqueConstraint('areaid', name='ocid_cell_area_areaid_unique'),
    )
    _valid_schema = None

    radio = Column(TinyIntEnum(Radio), autoincrement=False, default=None)
    mcc = Column(SmallInteger, autoincrement=False, default=None)
    mnc = Column(SmallInteger, autoincrement=False, default=None)
    lac = Column(SmallInteger(unsigned=True),
                 autoincrement=False, default=None)

    areaid = Column(CellAreaColumn(7), nullable=False)
    range = Column(Integer)
    avg_cell_range = Column(Integer)
    num_cells = Column(Integer(unsigned=True))


class ValidCellAreaOCIDSchema(ValidCellAreaKeySchema,
                              ValidPositionSchema,
                              ValidTimeTrackingSchema):

    # areaid is a derived value
    radius = colander.SchemaNode(colander.Integer(), missing=0)
    country = colander.SchemaNode(colander.String(), missing=None)
    avg_cell_radius = colander.SchemaNode(colander.Integer(), missing=0)
    num_cells = colander.SchemaNode(colander.Integer(), missing=0)


class CellAreaOCID(PositionMixin, TimeTrackingMixin, CreationMixin, _Model):
    __tablename__ = 'cell_area_ocid'

    _indices = (
        PrimaryKeyConstraint('areaid'),
        UniqueConstraint('radio', 'mcc', 'mnc', 'lac',
                         name='cell_area_ocid_areaid_unique'),
        Index('cell_area_ocid_country_radio_idx', 'country', 'radio'),
        Index('cell_area_ocid_created_idx', 'created'),
        Index('cell_area_ocid_modified_idx', 'modified'),
        Index('cell_area_ocid_latlon_idx', 'lat', 'lon'),
    )
    _valid_schema = ValidCellAreaOCIDSchema()

    areaid = Column(CellAreaColumn(7))
    radio = Column(TinyIntEnum(Radio), autoincrement=False, nullable=False)
    mcc = Column(SmallInteger, autoincrement=False, nullable=False)
    mnc = Column(SmallInteger, autoincrement=False, nullable=False)
    lac = Column(SmallInteger(unsigned=True),
                 autoincrement=False, nullable=False)

    radius = Column(Integer)
    country = Column(String(2))
    avg_cell_radius = Column(Integer(unsigned=True))
    num_cells = Column(Integer(unsigned=True))

    @classmethod
    def validate(cls, entry, _raise_invalid=False, **kw):
        validated = super(CellAreaOCID, cls).validate(
            entry, _raise_invalid=_raise_invalid, **kw)
        if validated is not None:
            if 'areaid' not in validated or not validated['areaid']:
                validated['areaid'] = (
                    validated['radio'],
                    validated['mcc'],
                    validated['mnc'],
                    validated['lac'],
                )
            if (('country' not in validated or not validated['country']) and
                    validated['lat'] is not None and
                    validated['lon'] is not None):
                validated['country'] = GEOCODER.region(
                    validated['lat'], validated['lon'])
        return validated


class CellBlocklist(HashKeyQueryMixin, _Model):
    __tablename__ = 'cell_blacklist'

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac', 'cid'),
    )

    _hashkey_cls = CellKey
    _query_batch = 20

    radio = Column(TinyIntEnum(Radio), autoincrement=False, default=None)
    mcc = Column(SmallInteger, autoincrement=False, default=None)
    mnc = Column(SmallInteger, autoincrement=False, default=None)
    lac = Column(SmallInteger(unsigned=True),
                 autoincrement=False, default=None)
    cid = Column(Integer(unsigned=True), autoincrement=False, default=None)
    time = Column(DateTime)
    count = Column(Integer)


class ValidCellSchema(ValidCellKeySchema, ValidBboxSchema,
                      ValidPositionSchema, ValidTimeTrackingSchema):
    """A schema which validates the fields in a cell."""

    range = colander.SchemaNode(colander.Integer(), missing=0)
    total_measures = colander.SchemaNode(colander.Integer(), missing=0)


class Cell(BboxMixin, PositionMixin, TimeTrackingMixin,
           CreationMixin, HashKeyQueryMixin, _Model):
    __tablename__ = 'cell'

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac', 'cid'),
        Index('cell_created_idx', 'created'),
        Index('cell_modified_idx', 'modified'),
    )

    _hashkey_cls = CellKey
    _query_batch = 20
    _valid_schema = ValidCellSchema()

    radio = Column(TinyIntEnum(Radio), autoincrement=False, default=None)
    mcc = Column(SmallInteger, autoincrement=False, default=None)
    mnc = Column(SmallInteger, autoincrement=False, default=None)
    lac = Column(SmallInteger(unsigned=True),
                 autoincrement=False, default=None)
    cid = Column(Integer(unsigned=True), autoincrement=False, default=None)
    psc = Column(SmallInteger, autoincrement=False)
    range = Column(Integer)
    total_measures = Column(Integer(unsigned=True))
    new_measures = Column(Integer(unsigned=True))

    @property
    def areaid(self):
        return encode_cellarea(self.radio, self.mcc, self.mnc, self.lac)

    @property
    def radius(self):
        # BBB: alias
        return self.range

    @property
    def samples(self):
        # BBB: alias
        return self.total_measures


class OCIDCell(PositionMixin, TimeTrackingMixin,
               CreationMixin, HashKeyQueryMixin, _Model):
    # BBB
    __tablename__ = 'ocid_cell'

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac', 'cid'),
        Index('ocid_cell_created_idx', 'created'),
    )

    _hashkey_cls = CellKey
    _query_batch = 20
    _valid_schema = None

    radio = Column(TinyIntEnum(Radio), autoincrement=False, default=None)
    mcc = Column(SmallInteger, autoincrement=False, default=None)
    mnc = Column(SmallInteger, autoincrement=False, default=None)
    lac = Column(SmallInteger(unsigned=True),
                 autoincrement=False, default=None)
    cid = Column(Integer(unsigned=True), autoincrement=False, default=None)
    psc = Column(SmallInteger, autoincrement=False)
    range = Column(Integer)
    total_measures = Column(Integer(unsigned=True))
    changeable = Column(Boolean)


class ValidCellOCIDSchema(ValidCellKeySchema, ValidBboxSchema,
                          ValidPositionSchema, ValidTimeTrackingSchema):
    """A schema which validates the fields present in a :term:`OCID` cell."""

    radius = colander.SchemaNode(colander.Integer(), missing=0)
    country = colander.SchemaNode(colander.String(), missing=None)
    samples = colander.SchemaNode(colander.Integer(), missing=0)
    source = StationSourceNode(StationSourceType(), missing=None)

    block_first = colander.SchemaNode(DateFromString(), missing=None)
    block_last = colander.SchemaNode(DateFromString(), missing=None)
    block_count = colander.SchemaNode(colander.Integer(), missing=0)


class CellOCID(BboxMixin, PositionMixin, TimeTrackingMixin,
               CreationMixin, _Model):
    __tablename__ = 'cell_ocid'

    _indices = (
        PrimaryKeyConstraint('cellid'),
        UniqueConstraint('radio', 'mcc', 'mnc', 'lac', 'cid',
                         name='cell_ocid_cellid_unique'),
        Index('cell_ocid_country_radio_idx', 'country', 'radio'),
        Index('cell_ocid_created_idx', 'created'),
        Index('cell_ocid_modified_idx', 'modified'),
        Index('cell_ocid_latlon_idx', 'lat', 'lon'),
    )
    _valid_schema = ValidCellOCIDSchema()

    cellid = Column(CellIdColumn(11))
    radio = Column(TinyIntEnum(Radio), autoincrement=False, nullable=False)
    mcc = Column(SmallInteger, autoincrement=False, nullable=False)
    mnc = Column(SmallInteger, autoincrement=False, nullable=False)
    lac = Column(SmallInteger(unsigned=True),
                 autoincrement=False, nullable=False)
    cid = Column(Integer(unsigned=True), autoincrement=False, nullable=False)
    psc = Column(SmallInteger, autoincrement=False)

    radius = Column(Integer(unsigned=True))
    country = Column(String(2))
    samples = Column(Integer(unsigned=True))
    source = Column(TinyIntEnum(StationSource))

    block_first = Column(Date)
    block_last = Column(Date)
    block_count = Column(TinyInteger(unsigned=True))

    @classmethod
    def validate(cls, entry, _raise_invalid=False, **kw):
        validated = super(CellOCID, cls).validate(
            entry, _raise_invalid=_raise_invalid, **kw)
        if validated is not None:
            if 'cellid' not in validated:
                validated['cellid'] = (
                    validated['radio'],
                    validated['mcc'],
                    validated['mnc'],
                    validated['lac'],
                    validated['cid'],
                )
            if (('country' not in validated or not validated['country']) and
                    validated['lat'] is not None and
                    validated['lon'] is not None):
                validated['country'] = GEOCODER.region(
                    validated['lat'], validated['lon'])
        return validated

    @property
    def areaid(self):
        return encode_cellarea(self.radio, self.mcc, self.mnc, self.lac)
