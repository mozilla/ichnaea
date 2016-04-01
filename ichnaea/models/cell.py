import base64
import math
import struct

import colander
from sqlalchemy import (
    BINARY,
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
)
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.types import TypeDecorator

from ichnaea.geocode import GEOCODER
from ichnaea.models.base import (
    _Model,
    CreationMixin,
)
from ichnaea.models import constants
from ichnaea.models.constants import Radio
from ichnaea.models.sa_types import (
    TinyIntEnum,
)
from ichnaea.models.schema import (
    DateFromString,
    DefaultNode,
    ValidatorNode,
)
from ichnaea.models.station import (
    PositionMixin,
    ScoreMixin,
    StationMixin,
    TimeTrackingMixin,
    ValidPositionSchema,
    ValidStationSchema,
    ValidTimeTrackingSchema,
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

CELL_SHARDS = {}
CELL_SHARDS_OCID = {}


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

    age = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(
            constants.MIN_AGE, constants.MAX_AGE))

    asu = DefaultNode(
        colander.Integer(),
        missing=None, validator=colander.Range(
            min(constants.MIN_CELL_ASU.values()),
            max(constants.MAX_CELL_ASU.values())))

    signal = DefaultNode(
        colander.Integer(),
        missing=None, validator=colander.Range(
            min(constants.MIN_CELL_SIGNAL.values()),
            max(constants.MAX_CELL_SIGNAL.values())))

    ta = DefaultNode(
        colander.Integer(),
        missing=None, validator=colander.Range(
            constants.MIN_CELL_TA, constants.MAX_CELL_TA))

    def _signal_from_asu(self, radio, value):
        if radio is Radio.gsm:
            return (value * 2) - 113
        if radio is Radio.wcdma:
            return value - 116
        if radio is Radio.lte:
            return value - 140

    def deserialize(self, data):
        if data:
            # Sometimes the asu and signal fields are swapped
            if (data.get('asu') is not None and
                    data.get('asu', 0) < -5 and
                    (data.get('signal') is None or
                     data.get('signal', 0) >= 0)):
                # shallow copy
                data = dict(data)
                data['signal'] = data['asu']
                data['asu'] = None

        data = super(ValidCellSignalSchema, self).deserialize(data)

        if isinstance(data.get('radio'), Radio):
            radio = data['radio']

            # Radio type specific checks for ASU field
            if data.get('asu') is not None:
                if not (constants.MIN_CELL_ASU[radio] <=
                        data['asu'] <=
                        constants.MAX_CELL_ASU[radio]):
                    data = dict(data)
                    data['asu'] = None

            # Radio type specific checks for signal field
            if data.get('signal') is not None:
                if not (constants.MIN_CELL_SIGNAL[radio] <=
                        data['signal'] <=
                        constants.MAX_CELL_SIGNAL[radio]):
                    data = dict(data)
                    data['signal'] = None

            # Radio type specific checks for TA field
            if data.get('ta') is not None and radio is Radio.wcdma:
                data = dict(data)
                data['ta'] = None

            # Calculate signal from ASU field
            if data.get('asu') is not None and data.get('signal') is None:
                if (constants.MIN_CELL_ASU[radio] <= data['asu'] <=
                        constants.MAX_CELL_ASU[radio]):
                    data = dict(data)
                    data['signal'] = self._signal_from_asu(radio, data['asu'])

        return data


class ValidCellAreaSchema(ValidCellAreaKeySchema,
                          ValidPositionSchema,
                          ValidTimeTrackingSchema):

    # areaid is a derived value
    radius = colander.SchemaNode(
        colander.Integer(), missing=0,
        validator=colander.Range(0, constants.CELLAREA_MAX_RADIUS))
    region = colander.SchemaNode(colander.String(), missing=None)
    avg_cell_radius = colander.SchemaNode(colander.Integer(), missing=0)
    num_cells = colander.SchemaNode(colander.Integer(), missing=0)
    last_seen = colander.SchemaNode(DateFromString(), missing=None)


class CellAreaMixin(PositionMixin, TimeTrackingMixin,
                    CreationMixin, ScoreMixin):

    _valid_schema = ValidCellAreaSchema()

    areaid = Column(CellAreaColumn(7))  #:
    radio = Column(TinyIntEnum(Radio), autoincrement=False, nullable=False)  #:
    mcc = Column(SmallInteger, autoincrement=False, nullable=False)  #:
    mnc = Column(SmallInteger, autoincrement=False, nullable=False)  #:
    lac = Column(SmallInteger(unsigned=True),
                 autoincrement=False, nullable=False)  #:

    radius = Column(Integer)  #:
    region = Column(String(2))  #:
    avg_cell_radius = Column(Integer(unsigned=True))  #:
    num_cells = Column(Integer(unsigned=True))  #:
    last_seen = Column(Date)  #:

    def score_sample_weight(self):
        # treat areas for which we get the exact same
        # cells multiple times as if we only got 1 cell
        samples = self.num_cells
        if samples > 1 and not self.radius:
            samples = 1

        # sample_weight is a number between:
        # 1.0 for 1 sample
        # 1.41 for 2 samples
        # 10 for 100 samples
        # we use a sqrt scale instead of log2 here, as this represents
        # the number of cells in an area and not the sum of samples
        # from all cells in the area
        return min(math.sqrt(max(samples, 1)), 10.0)

    def score_created_position(self):
        return self.created.date()

    @declared_attr
    def __table_args__(cls):  # NOQA
        prefix = cls.__tablename__
        _indices = (
            PrimaryKeyConstraint('areaid'),
            UniqueConstraint('radio', 'mcc', 'mnc', 'lac',
                             name='%s_areaid_unique' % prefix),
            Index('%s_region_radio_idx' % prefix, 'region', 'radio'),
            Index('%s_created_idx' % prefix, 'created'),
            Index('%s_modified_idx' % prefix, 'modified'),
            Index('%s_latlon_idx' % prefix, 'lat', 'lon'),
        )
        return _indices + (cls._settings, )

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

            if (('region' not in validated or not validated['region']) and
                    validated['lat'] is not None and
                    validated['lon'] is not None):
                validated['region'] = GEOCODER.region_for_cell(
                    validated['lat'], validated['lon'], validated['mcc'])

        return validated


class CellArea(CellAreaMixin, _Model):
    """CellArea model."""

    __tablename__ = 'cell_area'


class CellAreaOCID(CellAreaMixin, _Model):
    """CellArea OCID model."""

    __tablename__ = 'cell_area_ocid'


class ValidCellShardSchema(ValidCellKeySchema, ValidStationSchema):

    # adds a range validator
    radius = colander.SchemaNode(
        colander.Integer(), missing=0,
        validator=colander.Range(0, constants.CELL_MAX_RADIUS))


class BaseCell(StationMixin):

    _valid_schema = ValidCellShardSchema()

    cellid = Column(CellIdColumn(11))
    radio = Column(TinyIntEnum(Radio), autoincrement=False, nullable=False)
    mcc = Column(SmallInteger, autoincrement=False, nullable=False)
    mnc = Column(SmallInteger, autoincrement=False, nullable=False)
    lac = Column(SmallInteger(unsigned=True),
                 autoincrement=False, nullable=False)
    cid = Column(Integer(unsigned=True), autoincrement=False, nullable=False)
    psc = Column(SmallInteger, autoincrement=False)

    @classmethod
    def validate(cls, entry, _raise_invalid=False, **kw):
        validated = super(BaseCell, cls).validate(
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

            if (('region' not in validated or not validated['region']) and
                    validated['lat'] is not None and
                    validated['lon'] is not None):
                validated['region'] = GEOCODER.region_for_cell(
                    validated['lat'], validated['lon'], validated['mcc'])

        return validated

    @property
    def areaid(self):
        return encode_cellarea(self.radio, self.mcc, self.mnc, self.lac)

    @property
    def unique_key(self):
        return encode_cellid(*self.cellid)


class CellOCID(BaseCell, _Model):
    """Cell OCID model."""
    # BBB

    __tablename__ = 'cell_ocid'

    _indices = (
        PrimaryKeyConstraint('cellid'),
        UniqueConstraint('radio', 'mcc', 'mnc', 'lac', 'cid',
                         name='cell_ocid_cellid_unique'),
        Index('cell_ocid_region_radio_idx', 'region', 'radio'),
        Index('cell_ocid_created_idx', 'created'),
        Index('cell_ocid_modified_idx', 'modified'),
        Index('cell_ocid_latlon_idx', 'lat', 'lon'),
    )

    @classmethod
    def shard_id(cls, radio):  # pragma: no cover
        return 'ocid'

    @classmethod
    def shard_model(cls, radio):  # pragma: no cover
        return cls

    @classmethod
    def shards(cls):  # pragma: no cover
        return {'ocid': cls}


class CellShard(BaseCell):
    """Cell shard."""

    _shards = CELL_SHARDS

    @declared_attr
    def __table_args__(cls):  # NOQA
        _indices = (
            PrimaryKeyConstraint('cellid'),
            UniqueConstraint('radio', 'mcc', 'mnc', 'lac', 'cid',
                             name='%s_cellid_unique' % cls.__tablename__),
            Index('%s_region_idx' % cls.__tablename__, 'region'),
            Index('%s_created_idx' % cls.__tablename__, 'created'),
            Index('%s_modified_idx' % cls.__tablename__, 'modified'),
            Index('%s_latlon_idx' % cls.__tablename__, 'lat', 'lon'),
        )
        return _indices + (cls._settings, )

    @classmethod
    def create(cls, _raise_invalid=False, **kw):
        """
        Returns an instance of the correct shard model class, if the
        passed in keyword arguments pass schema validation,
        otherwise returns None.
        """
        validated = cls.validate(kw, _raise_invalid=_raise_invalid)
        if validated is None:  # pragma: no cover
            return None
        shard = cls.shard_model(validated['radio'])
        return shard(**validated)

    @classmethod
    def shard_id(cls, radio):
        """
        Given a radio type return the correct shard id.
        """
        if type(radio) == bytes and len(radio) == 11:
            # extract radio from cellid
            radio = decode_cellid(radio)[0]
        if type(radio) == Radio:
            return radio.name
        if isinstance(radio, tuple) and len(radio) == 5:
            return radio[0].name
        try:
            return Radio[radio].name
        except KeyError:
            pass
        return None

    @classmethod
    def shard_model(cls, radio):
        """
        Given a radio type return the correct DB model class.
        """
        return cls._shards.get(cls.shard_id(radio), None)

    @classmethod
    def shards(cls):
        """Return a dict of shard id to model classes."""
        return cls._shards


class CellShardOCID(CellShard):
    """Cell OCID shard."""

    _shards = CELL_SHARDS_OCID


class CellShardGsm(CellShard, _Model):
    """Shard for GSM cells."""

    __tablename__ = 'cell_gsm'

CELL_SHARDS[Radio.gsm.name] = CellShardGsm


class CellShardGsmOCID(CellShardOCID, _Model):
    """Shard for GSM OCID cells."""

    __tablename__ = 'cell_gsm_ocid'

CELL_SHARDS_OCID[Radio.gsm.name] = CellShardGsmOCID


class CellShardWcdma(CellShard, _Model):
    """Shard for WCDMA cells."""

    __tablename__ = 'cell_wcdma'

CELL_SHARDS[Radio.wcdma.name] = CellShardWcdma


class CellShardWcdmaOCID(CellShardOCID, _Model):
    """Shard for WCDMA OCID cells."""

    __tablename__ = 'cell_wcdma_ocid'

CELL_SHARDS_OCID[Radio.wcdma.name] = CellShardWcdmaOCID


class CellShardLte(CellShard, _Model):
    """Shard for LTE cells."""

    __tablename__ = 'cell_lte'

CELL_SHARDS[Radio.lte.name] = CellShardLte


class CellShardLteOCID(CellShardOCID, _Model):
    """Shard for LTE OCID cells."""

    __tablename__ = 'cell_lte_ocid'

CELL_SHARDS_OCID[Radio.lte.name] = CellShardLteOCID
