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
    HashKey,
    HashKeyMixin,
    PositionMixin,
    TimeTrackingMixin,
    ValidationMixin,
)
from ichnaea.models.sa_types import TinyIntEnum
from ichnaea.models.station import (
    BaseStationMixin,
    StationMixin,
    StationBlacklistMixin,
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


class CellAreaKey(CellHashKey):

    _fields = ('radio', 'mcc', 'mnc', 'lac')


class CellKey(CellHashKey):

    _fields = ('radio', 'mcc', 'mnc', 'lac', 'cid')


class CellKeyPsc(CellHashKey):

    _fields = ('radio', 'mcc', 'mnc', 'lac', 'cid', 'psc')


class CellAreaKeyMixin(HashKeyMixin):

    _hashkey_cls = CellAreaKey

    radio = Column(TinyIntEnum(Radio), autoincrement=False)
    mcc = Column(SmallInteger, autoincrement=False)
    mnc = Column(SmallInteger, autoincrement=False)
    lac = Column(SmallInteger(unsigned=True), autoincrement=False)


class CellAreaMixin(CellAreaKeyMixin, TimeTrackingMixin, PositionMixin):

    range = Column(Integer)
    avg_cell_range = Column(Integer)
    num_cells = Column(Integer(unsigned=True))


class CellKeyMixin(CellAreaKeyMixin):

    _hashkey_cls = CellKey

    cid = Column(Integer(unsigned=True), autoincrement=False)


class CellKeyPscMixin(CellKeyMixin):

    _hashkey_cls = CellKeyPsc

    psc = Column(SmallInteger, autoincrement=False)


class CellMixin(CellKeyPscMixin):

    _hashkey_cls = CellKey


class Cell(CellMixin, StationMixin, _Model):
    __tablename__ = 'cell'

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac', 'cid'),
        Index('cell_created_idx', 'created'),
        Index('cell_modified_idx', 'modified'),
        Index('cell_new_measures_idx', 'new_measures'),
        Index('cell_total_measures_idx', 'total_measures'),
    )

    def __init__(self, *args, **kw):
        if 'new_measures' not in kw:
            kw['new_measures'] = 0
        if 'total_measures' not in kw:
            kw['total_measures'] = 0
        super(Cell, self).__init__(*args, **kw)


class OCIDCell(CellMixin, BaseStationMixin, ValidationMixin, _Model):
    __tablename__ = 'ocid_cell'

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac', 'cid'),
        Index('ocid_cell_created_idx', 'created'),
    )

    changeable = Column(Boolean)

    @classmethod
    def valid_schema(cls):
        from ichnaea.data.schema import ValidOCIDCellSchema
        return ValidOCIDCellSchema

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
