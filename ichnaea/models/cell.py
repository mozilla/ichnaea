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
        if cstruct is None or cstruct is colander.null:  # pragma: no cover
            return True
        raise colander.Invalid(node, 'Invalid radio type')  # pragma: no cover


class RadioType(colander.Integer):
    """
    A RadioType will return a Radio IntEnum object.
    """

    def deserialize(self, node, cstruct):
        if cstruct is colander.null:  # pragma: no cover
            return colander.null
        if isinstance(cstruct, Radio):
            return cstruct
        try:
            if isinstance(cstruct, basestring):
                cstruct = Radio[cstruct]
            else:
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

    radio = RadioNode(RadioType(), missing=None)
    mcc = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(1, 999))
    mnc = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(0, 32767))
    lac = DefaultNode(
        colander.Integer(),
        missing=0,
        validator=colander.Range(
            constants.MIN_LAC, constants.MAX_LAC_ALL))


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
        missing=0, validator=colander.Range(
            constants.MIN_CID, constants.MAX_CID_ALL))
    psc = DefaultNode(
        colander.Integer(),
        missing=-1,
        validator=colander.Range(0, 512))

    def deserialize(self, data, default_radio=None):
        if data:
            # deserialize radio child field early
            data['radio'] = self.fields['radio'].deserialize(data['radio'])

            # If a default radio was set,
            # and we don't know, use it as fallback
            if (self.is_missing(data, 'radio')
                    and default_radio is not None):
                data['radio'] = self.fields['radio'].deserialize(default_radio)

            # If the cell id >= 65536 then it must be a umts tower
            if (data.get('cid', 0) >= 65536
                    and data['radio'] == Radio.gsm):
                data['radio'] = Radio.umts

            # Treat cid=65535 without a valid lac as an unspecified value
            if (self.is_missing(data, 'lac')
                    and data.get('cid', None) == 65535):
                data['cid'] = self.fields['cid'].missing

        return super(ValidCellKeySchema, self).deserialize(data)

    def validator(self, schema, data):
        lac_missing = self.is_missing(data, 'lac')
        cid_missing = self.is_missing(data, 'cid')

        if data['mcc'] not in constants.ALL_VALID_MCCS:
            raise colander.Invalid(schema, (
                'Check against the list of all known valid mccs'))

        if (data['radio'] == Radio.cdma
                and (lac_missing or cid_missing)):
            raise colander.Invalid(schema, (
                'Skip CDMA towers missing lac or cid '
                '(no psc on CDMA exists to backfill using inference)'))

        if data['radio'] in Radio._gsm_family() and data['mnc'] > 999:
            raise colander.Invalid(schema, (
                'Skip GSM/LTE/UMTS towers with an invalid MNC'))

        if ((lac_missing or cid_missing) and self.is_missing(data, 'psc')):
            raise colander.Invalid(schema, (
                'Must have (lac and cid) or '
                'psc (psc-only to use in backfill)'))

        if (data['radio'] == Radio.cdma
                and data['cid'] > constants.MAX_CID_CDMA):
            raise colander.Invalid(schema, (
                'CID is out of range for CDMA.'))

        if (data['radio'] == Radio.lte
                and data['cid'] > constants.MAX_CID_LTE):
            raise colander.Invalid(schema, (
                'CID is out of range for LTE.'))

        if (data['radio'] in Radio._gsm_family()
                and data['lac'] > constants.MAX_LAC_GSM_UMTS_LTE):
            raise colander.Invalid(schema, (
                'LAC is out of range for GSM/UMTS/LTE.'))


class CellKeyMixin(CellAreaKeyMixin):

    _hashkey_cls = CellKey

    cid = Column(Integer(unsigned=True), autoincrement=False)


class CellKeyPscMixin(CellKeyMixin):

    _hashkey_cls = CellKeyPsc

    psc = Column(SmallInteger, autoincrement=False)


class CellMixin(CellKeyPscMixin):

    _hashkey_cls = CellKey


class ValidCellSchema(ValidCellKeySchema, ValidStationSchema):
    """A schema which validates the fields in cell."""

    new_measures = colander.SchemaNode(colander.Integer(), missing=0)


class Cell(CellMixin, StationMixin, CreationMixin, _Model):
    __tablename__ = 'cell'

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac', 'cid'),
        Index('cell_created_idx', 'created'),
        Index('cell_modified_idx', 'modified'),
        Index('cell_new_measures_idx', 'new_measures'),
    )
    _valid_schema = ValidCellSchema

    def __init__(self, *args, **kw):
        if 'new_measures' not in kw:
            kw['new_measures'] = 0
        if 'total_measures' not in kw:
            kw['total_measures'] = 0
        super(Cell, self).__init__(*args, **kw)


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
