import datetime
import re

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import INTEGER as Integer
from sqlalchemy.dialects.mysql import BIGINT as BigInteger

from ichnaea.db import _VolatileModel, _ArchivalModel

# Latitudes and longitudes are stored as degrees * 10**7,
# or equivalently: as an integer count of 1E-7ths of a degree.
# This is done so that we can treat them with integer types;
# 1E-7 degrees =~ 1.1cm, so that is our spatial resolution.
DEGREE_DECIMAL_PLACES = 7
DEGREE_SCALE_FACTOR = 10 ** DEGREE_DECIMAL_PLACES

RADIO_TYPE = {
    '': -1,
    'gsm': 0,
    'cdma': 1,
    'umts': 2,
    'lte': 3,
}
RADIO_TYPE_KEYS = list(RADIO_TYPE.keys())
RADIO_TYPE_INVERSE = dict((v, k) for k, v in RADIO_TYPE.items())

invalid_wifi_regex = re.compile("(?!(0{12}|f{12}))")
valid_wifi_regex = re.compile("([0-9a-fA-F]{12})")


def from_degrees(deg):
    return int(deg * DEGREE_SCALE_FACTOR)


def to_degrees(i):
    return float(i) / DEGREE_SCALE_FACTOR


def valid_wifi_pattern(key):
    return invalid_wifi_regex.match(key) and \
        valid_wifi_regex.match(key) and len(key) == 12


def normalize_wifi_key(key):
    if ":" in key or "-" in key or "." in key:
        key = key.replace(":", "").replace("-", "").replace(".", "")
    return key.lower()


class Cell(_VolatileModel):
    __tablename__ = 'cell'
    __table_args__ = (
        UniqueConstraint(
            'radio', 'mcc', 'mnc', 'lac', 'cid', name='cell_idx_unique'),
        Index('cell_created_idx', 'created'),
        Index('cell_new_measures_idx', 'new_measures'),
        Index('cell_total_measures_idx', 'total_measures'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
        }
    )

    id = Column(BigInteger(unsigned=True),
                primary_key=True, autoincrement=True)
    created = Column(DateTime)

    # lat/lon * DEGREE_SCALE_FACTOR
    lat = Column(Integer)
    max_lat = Column(Integer)
    min_lat = Column(Integer)

    lon = Column(Integer)
    max_lon = Column(Integer)
    min_lon = Column(Integer)

    # mapped via RADIO_TYPE
    radio = Column(SmallInteger)
    # int in the range 0-1000
    mcc = Column(SmallInteger)
    # int in the range 0-1000 for gsm
    # int in the range 0-32767 for cdma (system id)
    mnc = Column(Integer)
    lac = Column(Integer)
    cid = Column(Integer)
    psc = Column(Integer)
    range = Column(Integer)
    new_measures = Column(Integer(unsigned=True))
    total_measures = Column(Integer(unsigned=True))

    def __init__(self, *args, **kw):
        if 'created' not in kw:
            kw['created'] = datetime.datetime.utcnow()
        if 'lac' not in kw:
            kw['lac'] = -1
        if 'cid' not in kw:
            kw['cid'] = -1
        if 'new_measures' not in kw:
            kw['new_measures'] = 0
        if 'total_measures' not in kw:
            kw['total_measures'] = 0
        super(Cell, self).__init__(*args, **kw)

cell_table = Cell.__table__


class CellBlacklist(_VolatileModel):
    __tablename__ = 'cell_blacklist'
    __table_args__ = (
        UniqueConstraint('radio', 'mcc', 'mnc', 'lac', 'cid',
                         name='cell_blacklist_idx_unique'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
        }
    )
    id = Column(BigInteger(unsigned=True),
                primary_key=True, autoincrement=True)
    created = Column(DateTime)
    radio = Column(SmallInteger)
    mcc = Column(SmallInteger)
    mnc = Column(Integer)
    lac = Column(Integer)
    cid = Column(Integer)

    def __init__(self, *args, **kw):
        if 'created' not in kw:
            kw['created'] = datetime.datetime.utcnow()
        super(CellBlacklist, self).__init__(*args, **kw)


class CellMeasure(_ArchivalModel):
    __tablename__ = 'cell_measure'
    __table_args__ = (
        Index('cell_measure_created_idx', 'created'),
        Index('cell_measure_key_idx', 'radio', 'mcc', 'mnc', 'lac', 'cid'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'compressed',
            'mysql_key_block_size': '4',
        }
    )

    id = Column(BigInteger(unsigned=True),
                primary_key=True, autoincrement=True)
    measure_id = Column(BigInteger(unsigned=True))
    created = Column(DateTime)  # the insert time of the record into the DB
    # lat/lon * DEGREE_SCALE_FACTOR
    lat = Column(Integer)
    lon = Column(Integer)
    time = Column(DateTime)  # the time of observation of this data
    accuracy = Column(Integer)
    altitude = Column(Integer)
    altitude_accuracy = Column(Integer)
    # mapped via RADIO_TYPE
    radio = Column(SmallInteger)
    mcc = Column(SmallInteger)
    mnc = Column(Integer)
    lac = Column(Integer)
    cid = Column(Integer)
    psc = Column(Integer)
    asu = Column(SmallInteger)
    signal = Column(SmallInteger)
    ta = Column(SmallInteger)

    def __init__(self, *args, **kw):
        if 'measure_id' not in kw:
            kw['measure_id'] = 0
        if 'created' not in kw:
            kw['created'] = datetime.datetime.utcnow()
        super(CellMeasure, self).__init__(*args, **kw)

cell_measure_table = CellMeasure.__table__


class Wifi(_VolatileModel):
    __tablename__ = 'wifi'
    __table_args__ = (
        UniqueConstraint('key', name='wifi_key_unique'),
        Index('wifi_created_idx', 'created'),
        Index('wifi_new_measures_idx', 'new_measures'),
        Index('wifi_total_measures_idx', 'total_measures'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
        }
    )

    id = Column(BigInteger(unsigned=True),
                primary_key=True, autoincrement=True)
    created = Column(DateTime)
    key = Column(String(12))

    # lat/lon * DEGREE_SCALE_FACTOR
    lat = Column(Integer)
    max_lat = Column(Integer)
    min_lat = Column(Integer)

    lon = Column(Integer)
    max_lon = Column(Integer)
    min_lon = Column(Integer)

    range = Column(Integer)
    new_measures = Column(Integer(unsigned=True))
    total_measures = Column(Integer(unsigned=True))

    def __init__(self, *args, **kw):
        if 'created' not in kw:
            kw['created'] = datetime.datetime.utcnow()
        if 'new_measures' not in kw:
            kw['new_measures'] = 0
        if 'total_measures' not in kw:
            kw['total_measures'] = 0
        super(Wifi, self).__init__(*args, **kw)

wifi_table = Wifi.__table__


class WifiBlacklist(_VolatileModel):
    __tablename__ = 'wifi_blacklist'
    __table_args__ = (
        UniqueConstraint('key', name='wifi_blacklist_key_unique'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
        }
    )
    id = Column(BigInteger(unsigned=True),
                primary_key=True, autoincrement=True)
    created = Column(DateTime)
    key = Column(String(12))

    def __init__(self, *args, **kw):
        if 'created' not in kw:
            kw['created'] = datetime.datetime.utcnow()
        super(WifiBlacklist, self).__init__(*args, **kw)


class WifiMeasure(_ArchivalModel):
    __tablename__ = 'wifi_measure'
    __table_args__ = (
        Index('wifi_measure_created_idx', 'created'),
        Index('wifi_measure_key_idx', 'key'),
        Index('wifi_measure_key_created_idx', 'key', 'created'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'compressed',
            'mysql_key_block_size': '4',
        }
    )

    id = Column(BigInteger(unsigned=True),
                primary_key=True, autoincrement=True)
    measure_id = Column(BigInteger(unsigned=True))
    created = Column(DateTime)  # the insert time of the record into the DB
    # lat/lon * DEGREE_SCALE_FACTOR
    lat = Column(Integer)
    lon = Column(Integer)
    time = Column(DateTime)  # the time of observation of this data
    accuracy = Column(Integer)
    altitude = Column(Integer)
    altitude_accuracy = Column(Integer)
    key = Column(String(12))
    channel = Column(SmallInteger)
    signal = Column(SmallInteger)

    def __init__(self, *args, **kw):
        if 'measure_id' not in kw:
            kw['measure_id'] = 0
        if 'created' not in kw:
            kw['created'] = datetime.datetime.utcnow()
        super(WifiMeasure, self).__init__(*args, **kw)

wifi_measure_table = WifiMeasure.__table__


class Measure(_ArchivalModel):
    __tablename__ = 'measure'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
    }

    id = Column(BigInteger(unsigned=True),
                primary_key=True, autoincrement=True)

measure_table = Measure.__table__
