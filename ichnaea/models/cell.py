import colander
from enum import IntEnum
from sqlalchemy import (
    Column,
    Index,
    Boolean,
    PrimaryKeyConstraint,
)
from sqlalchemy.dialects.mysql import (
    INTEGER as Integer,
    SMALLINT as SmallInteger,
    TINYINT as TinyInteger,
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
    HashKeyMixin,
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
    StationBlacklistMixin,
    ValidStationSchema,
)


class Radio(IntEnum):
    __order__ = 'gsm cdma umts wcdma lte'

    gsm = 0
    cdma = 1
    umts = 2
    wcdma = 2
    lte = 3

    @classmethod
    def _gsm_family(cls):
        return (cls.gsm, cls.umts, cls.lte)


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
        if type(cstruct) == Radio:
            return True
        raise colander.Invalid(node, 'Invalid radio type')


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
            if isinstance(cstruct, basestring):
                cstruct = Radio[cstruct]
            else:  # pragma: no cover
                cstruct = Radio(cstruct)
        except (KeyError, ValueError):
            raise colander.Invalid(node, (
                '%r is not a valid radio type' % cstruct))
        return cstruct


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

    def validator(self, schema, data):
        if data['mcc'] not in constants.ALL_VALID_MCCS:
            raise colander.Invalid(schema, (
                'Check against the list of all known valid mccs'))

        if data['radio'] in Radio._gsm_family() and data['mnc'] > 999:
            raise colander.Invalid(schema, (
                'Skip GSM/LTE/UMTS towers with an invalid MNC'))

        if (data['radio'] in Radio._gsm_family() and
                data['lac'] > constants.MAX_LAC_GSM_UMTS_LTE):
            raise colander.Invalid(schema, (
                'LAC is out of range for GSM/UMTS/LTE.'))


class CellAreaKeyMixin(HashKeyMixin):

    _hashkey_cls = CellAreaKey

    radio = Column(TinyIntEnum(Radio), autoincrement=False)
    mcc = Column(SmallInteger, autoincrement=False)
    mnc = Column(SmallInteger, autoincrement=False)
    lac = Column(SmallInteger(unsigned=True), autoincrement=False)


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

            # If the cell id >= 65536 then it must be a umts tower
            if data.get('cid', 0) >= 65536 and data['radio'] == Radio.gsm:
                data['radio'] = Radio.umts

            # Treat cid=65535 without a valid lac as an unspecified value
            if data.get('lac') is None and data.get('cid') == 65535:
                data['cid'] = None

        return super(ValidCellKeySchema, self).deserialize(data)

    def validator(self, schema, data):
        super(ValidCellKeySchema, self).validator(schema, data)

        lac_missing = data.get('lac') is None
        cid_missing = data.get('cid') is None
        psc_missing = data.get('psc') is None

        if data['radio'] == Radio.cdma and (lac_missing or cid_missing):
            raise colander.Invalid(schema, (
                'Skip CDMA towers missing lac or cid '
                '(no psc on CDMA exists to backfill using inference)'))

        if (lac_missing or cid_missing) and psc_missing:
            raise colander.Invalid(schema, (
                'Must have (lac and cid) or '
                'psc (psc-only to use in backfill)'))

        if (data['radio'] == Radio.cdma and
                data['cid'] > constants.MAX_CID_CDMA):
            raise colander.Invalid(schema, (
                'CID is out of range for CDMA.'))

        if (data['radio'] == Radio.lte and
                data['cid'] > constants.MAX_CID_LTE):
            raise colander.Invalid(schema, (
                'CID is out of range for LTE.'))


class CellKeyMixin(CellAreaKeyMixin):

    _hashkey_cls = CellKey

    cid = Column(Integer(unsigned=True), autoincrement=False)


class CellKeyPscMixin(CellKeyMixin):

    _hashkey_cls = CellKeyPsc

    psc = Column(SmallInteger, autoincrement=False)


class CellSignalMixin(object):

    asu = Column(SmallInteger)
    signal = Column(SmallInteger)
    ta = Column(TinyInteger)


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
            if data.get('asu', 0) < -1 and data.get('signal', None) == 0:
                data['signal'] = data['asu']
                data['asu'] = None
        return super(ValidCellSignalSchema, self).deserialize(data)


class CellMixin(CellKeyPscMixin):

    _hashkey_cls = CellKey


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


class ValidOCIDCellSchema(ValidCellKeySchema, ValidStationSchema):
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
