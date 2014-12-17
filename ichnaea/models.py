from collections import namedtuple

from sqlalchemy import (
    BINARY,
    Column,
    Float,
    Index,
    Boolean,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import (
    BIGINT as BigInteger,
    DOUBLE as Double,
    INTEGER as Integer,
    SMALLINT as SmallInteger,
    TINYINT as TinyInteger,
)
from ichnaea.db import _Model
from ichnaea.sa_types import TZDateTime as DateTime
from ichnaea import util

MEASURE_TYPE_CODE = {
    'wifi': 1,
    'cell': 2,
}
MEASURE_TYPE_CODE_INVERSE = dict((v, k) for k, v in MEASURE_TYPE_CODE.items())

RADIO_TYPE = {
    '': -1,
    'gsm': 0,
    'cdma': 1,
    'umts': 2,
    'wcdma': 2,  # WCDMA is the main air interface for UMTS,
                 # but is the value the Google Geolocation API
                 # uses to refer to this radio family.
    'lte': 3,
}
RADIO_TYPE_KEYS = list(RADIO_TYPE.keys())
RADIO_TYPE_INVERSE = dict((v, k) for k, v in RADIO_TYPE.items() if v != 2)
RADIO_TYPE_INVERSE[2] = 'umts'
MAX_RADIO_TYPE = max(RADIO_TYPE.values())
MIN_RADIO_TYPE = min(RADIO_TYPE.values())

# Numeric constant used to indicate "virtual cells" for LACs, in db.
CELLID_LAC = -2

CellKey = namedtuple('CellKey', 'radio mcc mnc lac cid')
CellKeyPsc = namedtuple('CellKey', 'radio mcc mnc lac cid psc')
CellAreaKey = namedtuple('CellAreaKey', 'radio mcc mnc lac')
WifiKey = namedtuple('WifiKey', 'key')


def to_cellkey(obj):
    """
    Construct a CellKey from any object with the requisite 5 fields.
    """
    if isinstance(obj, dict):
        return CellKey(radio=obj['radio'],
                       mcc=obj['mcc'],
                       mnc=obj['mnc'],
                       lac=obj['lac'],
                       cid=obj['cid'])
    else:
        return CellKey(radio=obj.radio,
                       mcc=obj.mcc,
                       mnc=obj.mnc,
                       lac=obj.lac,
                       cid=obj.cid)


def to_cellkey_psc(obj):
    """
    Construct a CellKeyPsc from any object with the requisite 6 fields.
    """
    if isinstance(obj, dict):
        return CellKeyPsc(radio=obj['radio'],
                          mcc=obj['mcc'],
                          mnc=obj['mnc'],
                          lac=obj['lac'],
                          cid=obj['cid'],
                          psc=obj['psc'])
    else:
        return CellKeyPsc(radio=obj.radio,
                          mcc=obj.mcc,
                          mnc=obj.mnc,
                          lac=obj.lac,
                          cid=obj.cid,
                          psc=obj.psc)


def join_cellkey(model, k):
    """
    Return an sqlalchemy equality criterion for joining on the cell n-tuple.
    Should be spliced into a query filter call like so:
    ``session.query(Cell).filter(*join_cellkey(Cell, k))``
    """
    criterion = (model.radio == k.radio,
                 model.mcc == k.mcc,
                 model.mnc == k.mnc,
                 model.lac == k.lac)
    # if the model has a psc column, and we get a CellKeyPsc,
    # add it to the criterion
    if isinstance(k, CellKeyPsc) and getattr(model, 'psc', None) is not None:
        criterion += (model.psc == k.psc, )

    if hasattr(model, 'cid') and hasattr(k, 'cid'):
        criterion += (model.cid == k.cid, )
    return criterion


def to_wifikey(obj):
    if isinstance(obj, dict):  # pragma: no cover
        return WifiKey(key=obj['key'])
    elif isinstance(obj, basestring):  # pragma: no cover
        return WifiKey(key=obj)
    else:
        return WifiKey(key=obj.key)


def join_wifikey(model, k):
    return (model.key == k.key,)


class Cell(_Model):
    __tablename__ = 'cell'
    __table_args__ = (
        UniqueConstraint(
            'radio', 'mcc', 'mnc', 'lac', 'cid', name='cell_idx_unique'),
        Index('cell_created_idx', 'created'),
        Index('cell_modified_idx', 'modified'),
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
    modified = Column(DateTime)

    # lat/lon
    lat = Column(Double(asdecimal=False))
    max_lat = Column(Double(asdecimal=False))
    min_lat = Column(Double(asdecimal=False))

    lon = Column(Double(asdecimal=False))
    max_lon = Column(Double(asdecimal=False))
    min_lon = Column(Double(asdecimal=False))

    # mapped via RADIO_TYPE
    radio = Column(TinyInteger)
    # int in the range 0-1000
    mcc = Column(SmallInteger)
    # int in the range 0-1000 for gsm
    # int in the range 0-32767 for cdma (system id)
    mnc = Column(SmallInteger)
    lac = Column(Integer)
    cid = Column(Integer)
    psc = Column(SmallInteger)
    range = Column(Integer)
    new_measures = Column(Integer(unsigned=True))
    total_measures = Column(Integer(unsigned=True))

    def __init__(self, *args, **kw):
        if 'created' not in kw:
            kw['created'] = util.utcnow()
        if 'modified' not in kw:
            kw['modified'] = util.utcnow()
        if 'lac' not in kw:
            kw['lac'] = -1
        if 'cid' not in kw:
            kw['cid'] = -1
        if 'range' not in kw:
            kw['range'] = 0
        if 'new_measures' not in kw:
            kw['new_measures'] = 0
        if 'total_measures' not in kw:
            kw['total_measures'] = 0
        super(Cell, self).__init__(*args, **kw)

cell_table = Cell.__table__


# Cell record from OpenCellID
class OCIDCell(_Model):
    __tablename__ = 'ocid_cell'
    __table_args__ = (
        Index('ocid_cell_created_idx', 'created'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
        }
    )

    created = Column(DateTime)
    modified = Column(DateTime)

    # lat/lon
    lat = Column(Double(asdecimal=False))
    lon = Column(Double(asdecimal=False))

    # radio mapped via RADIO_TYPE
    radio = Column(TinyInteger,
                   autoincrement=False, primary_key=True)
    mcc = Column(SmallInteger,
                 autoincrement=False, primary_key=True)
    mnc = Column(SmallInteger,
                 autoincrement=False, primary_key=True)
    lac = Column(SmallInteger(unsigned=True),
                 autoincrement=False, primary_key=True)
    cid = Column(Integer(unsigned=True),
                 autoincrement=False, primary_key=True)

    psc = Column(SmallInteger)
    range = Column(Integer)
    total_measures = Column(Integer(unsigned=True))
    changeable = Column(Boolean)

    def __init__(self, *args, **kw):
        if 'created' not in kw:
            kw['created'] = util.utcnow()
        if 'modified' not in kw:
            kw['modified'] = util.utcnow()
        if 'lac' not in kw:
            kw['lac'] = -1
        if 'cid' not in kw:
            kw['cid'] = -1
        if 'range' not in kw:
            kw['range'] = 0
        if 'total_measures' not in kw:
            kw['total_measures'] = 0
        if 'changeable' not in kw:
            kw['changeable'] = True
        super(OCIDCell, self).__init__(*args, **kw)

    @property
    def min_lat(self):
        return util.add_meters_to_latitude(self.lat, -self.range)

    @property
    def max_lat(self):
        return util.add_meters_to_latitude(self.lat, self.range)

    @property
    def min_lon(self):
        return util.add_meters_to_longitude(self.lat, self.lon, -self.range)

    @property
    def max_lon(self):
        return util.add_meters_to_longitude(self.lat, self.lon, self.range)

ocid_cell_table = OCIDCell.__table__


# Cell area record
class CellArea(_Model):
    __tablename__ = 'cell_area'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
    }

    created = Column(DateTime)
    modified = Column(DateTime)

    # lat/lon
    lat = Column(Double(asdecimal=False))
    lon = Column(Double(asdecimal=False))

    # radio mapped via RADIO_TYPE
    radio = Column(TinyInteger,
                   autoincrement=False, primary_key=True)
    mcc = Column(SmallInteger,
                 autoincrement=False, primary_key=True)
    mnc = Column(SmallInteger,
                 autoincrement=False, primary_key=True)
    lac = Column(SmallInteger(unsigned=True),
                 autoincrement=False, primary_key=True)

    range = Column(Integer)
    avg_cell_range = Column(Integer)
    num_cells = Column(Integer(unsigned=True))

    def __init__(self, *args, **kw):
        if 'created' not in kw:
            kw['created'] = util.utcnow()
        if 'modified' not in kw:
            kw['modified'] = util.utcnow()
        if 'range' not in kw:
            kw['range'] = 0
        if 'avg_cell_range' not in kw:
            kw['avg_cell_range'] = 0
        if 'num_cells' not in kw:
            kw['num_cells'] = 0
        super(CellArea, self).__init__(*args, **kw)

cell_area_table = CellArea.__table__


# Cell record from OpenCellID
class OCIDCellArea(_Model):
    __tablename__ = 'ocid_cell_area'

    created = Column(DateTime)
    modified = Column(DateTime)

    # lat/lon
    lat = Column(Double(asdecimal=False))
    lon = Column(Double(asdecimal=False))

    # radio mapped via RADIO_TYPE
    radio = Column(TinyInteger,
                   autoincrement=False, primary_key=True)
    mcc = Column(SmallInteger,
                 autoincrement=False, primary_key=True)
    mnc = Column(SmallInteger,
                 autoincrement=False, primary_key=True)
    lac = Column(SmallInteger(unsigned=True),
                 autoincrement=False, primary_key=True)

    range = Column(Integer)
    avg_cell_range = Column(Integer)
    num_cells = Column(Integer(unsigned=True))

    def __init__(self, *args, **kw):
        if 'created' not in kw:
            kw['created'] = util.utcnow()
        if 'modified' not in kw:
            kw['modified'] = util.utcnow()
        if 'range' not in kw:
            kw['range'] = 0
        if 'avg_cell_range' not in kw:
            kw['avg_cell_range'] = 0
        if 'num_cells' not in kw:
            kw['num_cells'] = 0
        super(OCIDCellArea, self).__init__(*args, **kw)

ocid_cell_area_table = OCIDCellArea.__table__


class CellBlacklist(_Model):
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
    time = Column(DateTime)
    radio = Column(TinyInteger)
    mcc = Column(SmallInteger)
    mnc = Column(SmallInteger)
    lac = Column(Integer)
    cid = Column(Integer)
    count = Column(Integer)

    def __init__(self, *args, **kw):
        if 'time' not in kw:
            kw['time'] = util.utcnow()
        if 'count' not in kw:
            kw['count'] = 1
        super(CellBlacklist, self).__init__(*args, **kw)


class MeasureBlock(_Model):
    __tablename__ = 'measure_block'
    __table_args__ = (
        Index('idx_measure_block_archive_date', 'archive_date'),
        Index('idx_measure_block_s3_key', 's3_key'),
        Index('idx_measure_block_end_id', 'end_id'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'compressed',
            'mysql_key_block_size': '4',
        }
    )
    id = Column(BigInteger(unsigned=True),
                primary_key=True,
                autoincrement=True)
    measure_type = Column(SmallInteger)
    s3_key = Column(String(80))
    archive_date = Column(DateTime)
    archive_sha = Column(BINARY(length=20))
    start_id = Column(BigInteger(unsigned=True))
    end_id = Column(BigInteger(unsigned=True))


class CellMeasure(_Model):
    __tablename__ = 'cell_measure'
    __table_args__ = (
        Index('cell_measure_created_idx', 'created'),
        Index('cell_measure_key_idx', 'radio', 'mcc', 'mnc', 'lac', 'cid'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
        }
    )

    id = Column(BigInteger(unsigned=True),
                primary_key=True, autoincrement=True)
    report_id = Column(BINARY(length=16))
    created = Column(DateTime)  # the insert time of the record into the DB
    # lat/lon
    lat = Column(Double(asdecimal=False))
    lon = Column(Double(asdecimal=False))
    time = Column(DateTime)  # the time of observation of this data
    accuracy = Column(Integer)
    altitude = Column(Integer)
    altitude_accuracy = Column(Integer)

    # http://dev.w3.org/geo/api/spec-source.html#heading
    heading = Column(Float)

    # http://dev.w3.org/geo/api/spec-source.html#speed
    speed = Column(Float)

    # mapped via RADIO_TYPE
    radio = Column(TinyInteger)
    mcc = Column(SmallInteger)
    mnc = Column(SmallInteger)
    lac = Column(Integer)
    cid = Column(Integer)
    psc = Column(SmallInteger)
    asu = Column(SmallInteger)
    signal = Column(SmallInteger)
    ta = Column(TinyInteger)

    def __init__(self, *args, **kw):
        if 'created' not in kw:
            kw['created'] = util.utcnow()
        super(CellMeasure, self).__init__(*args, **kw)

cell_measure_table = CellMeasure.__table__


class Wifi(_Model):
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
    modified = Column(DateTime)
    key = Column(String(12))

    # lat/lon
    lat = Column(Double(asdecimal=False))
    max_lat = Column(Double(asdecimal=False))
    min_lat = Column(Double(asdecimal=False))

    lon = Column(Double(asdecimal=False))
    max_lon = Column(Double(asdecimal=False))
    min_lon = Column(Double(asdecimal=False))

    range = Column(Integer)
    new_measures = Column(Integer(unsigned=True))
    total_measures = Column(Integer(unsigned=True))

    def __init__(self, *args, **kw):
        if 'created' not in kw:
            kw['created'] = util.utcnow()
        if 'modified' not in kw:
            kw['modified'] = util.utcnow()
        if 'new_measures' not in kw:
            kw['new_measures'] = 0
        if 'total_measures' not in kw:
            kw['total_measures'] = 0
        super(Wifi, self).__init__(*args, **kw)

wifi_table = Wifi.__table__


class WifiBlacklist(_Model):
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
    time = Column(DateTime)
    key = Column(String(12))
    count = Column(Integer)

    def __init__(self, *args, **kw):
        if 'time' not in kw:
            kw['time'] = util.utcnow()
        if 'count' not in kw:
            kw['count'] = 1
        super(WifiBlacklist, self).__init__(*args, **kw)


class WifiMeasure(_Model):
    __tablename__ = 'wifi_measure'
    __table_args__ = (
        Index('wifi_measure_created_idx', 'created'),
        Index('wifi_measure_key_idx', 'key'),
        Index('wifi_measure_key_created_idx', 'key', 'created'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
        }
    )

    id = Column(BigInteger(unsigned=True),
                primary_key=True, autoincrement=True)
    report_id = Column(BINARY(length=16))
    created = Column(DateTime)  # the insert time of the record into the DB
    # lat/lon
    lat = Column(Double(asdecimal=False))
    lon = Column(Double(asdecimal=False))
    time = Column(DateTime)  # the time of observation of this data
    accuracy = Column(Integer)
    altitude = Column(Integer)
    altitude_accuracy = Column(Integer)

    # http://dev.w3.org/geo/api/spec-source.html#heading
    heading = Column(Float)

    # http://dev.w3.org/geo/api/spec-source.html#speed
    speed = Column(Float)

    key = Column(String(12))
    channel = Column(SmallInteger)
    signal = Column(SmallInteger)
    snr = Column(SmallInteger)

    def __init__(self, *args, **kw):
        if 'created' not in kw:
            kw['created'] = util.utcnow()
        super(WifiMeasure, self).__init__(*args, **kw)

wifi_measure_table = WifiMeasure.__table__


class ApiKey(_Model):
    __tablename__ = 'api_key'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
    }

    valid_key = Column(String(40),
                       primary_key=True)

    # Maximum number of requests per day
    maxreq = Column(Integer)
    # Extended logging enabled?
    log = Column(Boolean)
    # A readable short name used in metrics
    shortname = Column(String(40))
    # A contact address
    email = Column(String(255))
    # Some free form context / description
    description = Column(String(255))


api_key_table = ApiKey.__table__


# Keep at end of file, as it needs to stay below the *Measure models
MEASURE_TYPE_META = {
    1: {'class': WifiMeasure,
        'csv_name': 'wifi_measure.csv'},
    2: {'class': CellMeasure,
        'csv_name': 'cell_measure.csv'},
}


MODEL_KEYS = {
    'cell': Cell,
    'cell_area': CellArea,
    'ocid_cell': OCIDCell,
    'ocid_cell_area': OCIDCellArea,
}
