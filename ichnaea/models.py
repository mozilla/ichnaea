from collections import namedtuple
from datetime import date, datetime

from colander import iso8601
import mobile_codes
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
from ichnaea import constants
from ichnaea import geocalc
from ichnaea.db import _Model
from ichnaea.sa_types import TZDateTime as DateTime
from ichnaea import util

# Symbolic constant used in specs passed to normalization functions.
REQUIRED = object()

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
                 # but is the value google geolocation API
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

ALL_VALID_MCCS = frozenset(
    [int(country.mcc)
     for country in mobile_codes._countries()
     if isinstance(country.mcc, str)] +
    [int(code)
     for country in mobile_codes._countries()
     if isinstance(country.mcc, tuple)
     for code in country.mcc]
)

CellKey = namedtuple('CellKey', 'radio mcc mnc lac cid')
CellKeyPsc = namedtuple('CellKey', 'radio mcc mnc lac cid psc')
WifiKey = namedtuple('WifiKey', 'key')


def encode_datetime(obj):
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%dT%H:%M:%S.%f')
    elif isinstance(obj, date):
        return obj.strftime('%Y-%m-%d')
    raise TypeError(repr(obj) + " is not JSON serializable")


def decode_datetime(obj):
    try:
        return iso8601.parse_date(obj)
    except (iso8601.ParseError, TypeError):
        return util.utcnow()


def valid_wifi_pattern(key):
    return constants.INVALID_WIFI_REGEX.match(key) and \
        constants.VALID_WIFI_REGEX.match(key) and len(key) == 12


def normalized_wifi_key(key):
    if ":" in key or "-" in key or "." in key:
        key = key.replace(":", "").replace("-", "").replace(".", "")
    return key.lower()


def normalized_dict_value(d, k, lo, hi, default=REQUIRED):
    """
    Returns a dict value d[k] if within range [lo,hi]. If the
    Value is missing or out of range, return default, unless
    default is REQUIRED, in which case return None.
    """
    if k not in d or d[k] < lo or d[k] > hi:
        if default is REQUIRED:
            return None
        else:
            return default
    else:
        return d[k]


def normalized_dict(d, specs):
    """
    Returns a copy of the provided dict, with its values set to a default
    value if missing or outside a specified range. If any missing or
    out-of-range values were specified as REQUIRED, return None.

    Arguments:
    d -- a dict to normalize
    specs -- a dict mapping keys to (lo, hi, default) triples, where
             default may be the symbolic constant REQUIRED;
             if any REQUIRED fields are missing or out of
             range, return None.
    """
    if not isinstance(d, dict):
        return None

    n = {}
    for (k, (lo, hi, default)) in specs.items():
        v = normalized_dict_value(d, k, lo, hi, default)
        if v is None:
            return None
        n[k] = v

    # copy forward anything not specified
    for (k, v) in d.items():
        if k not in n:
            n[k] = v
    return n


def normalized_measure_dict(d):
    """
    Returns a normalized copy of the provided measurement dict d,
    or None if the dict was invalid.
    """
    d = normalized_dict(
        d, dict(lat=(constants.MIN_LAT, constants.MAX_LAT, REQUIRED),
                lon=(-180.0, 180.0, REQUIRED),
                heading=(0.0, constants.MAX_HEADING, -1.0),
                speed=(0, constants.MAX_SPEED, -1.0),
                altitude=(constants.MIN_ALTITUDE, constants.MAX_ALTITUDE, 0),
                altitude_accuracy=(0, constants.MAX_ALTITUDE_ACCURACY, 0),
                accuracy=(0, constants.MAX_ACCURACY, 0)))

    if d is None:
        return None

    if 'time' not in d:
        d['time'] = ''
    d['time'] = encode_datetime(decode_datetime(d['time']))
    return d


def normalized_wifi_channel(d):
    chan = int(d.get('channel', 0))

    if 0 < chan and chan < 166:
        return chan

    # if no explicit channel was given, calculate
    freq = d.get('frequency', 0)

    if 2411 < freq < 2473:
        # 2.4 GHz band
        return (freq - 2407) // 5

    elif 5169 < freq < 5826:
        # 5 GHz band
        return (freq - 5000) // 5

    return 0


def normalized_wifi_dict(d):
    """
    Returns a normalized copy of the provided wifi dict d,
    or None if the dict was invalid.
    """
    d = normalized_dict(
        d, dict(signal=(-200, -1, 0),
                signalToNoiseRatio=(0, 100, 0)))

    if d is None:
        return None

    if 'key' not in d:
        return None

    d['key'] = normalized_wifi_key(d['key'])

    if not valid_wifi_pattern(d['key']):
        return None

    d['channel'] = normalized_wifi_channel(d)
    d.pop('frequency', 0)

    return d


def normalized_wifi_measure_dict(d):
    """
    Returns a normalized copy of the provided wifi-measure dict d,
    or None if the dict was invalid.
    """
    d = normalized_wifi_dict(d)
    return normalized_measure_dict(d)


def normalized_cell_dict(d, default_radio=-1):
    """
    Returns a normalized copy of the provided cell dict d,
    or None if the dict was invalid.
    """
    if not isinstance(d, dict):
        return None

    d = d.copy()
    if 'radio' in d and isinstance(d['radio'], basestring):
        d['radio'] = RADIO_TYPE.get(d['radio'], -1)

    d = normalized_dict(
        d, dict(radio=(MIN_RADIO_TYPE, MAX_RADIO_TYPE, default_radio),
                mcc=(1, 999, REQUIRED),
                mnc=(0, 32767, REQUIRED),
                lac=(1, 65535, -1),
                cid=(1, 268435455, -1),
                psc=(0, 512, -1)))

    if d is None:
        return None

    # Tighten the MCC check even more
    if d['mcc'] not in ALL_VALID_MCCS:
        return None

    if d['radio'] == -1 and default_radio != -1:
        d['radio'] = default_radio

    # Skip CDMA towers missing lac or cid (no psc on CDMA exists to
    # backfill using inference)
    if d['radio'] == RADIO_TYPE['cdma'] and (d['lac'] < 0 or d['cid'] < 0):
        return None

    # Treat cid=65535 without a valid lac as an unspecified value
    if d['lac'] == -1 and d['cid'] == 65535:
        d['cid'] = -1

    # Must have LAC+CID or PSC
    if (d['lac'] == -1 or d['cid'] == -1) and d['psc'] == -1:
        return None

    return d


def normalized_cell_measure_dict(d, measure_radio=-1):
    """
    Returns a normalized copy of the provided cell-measure dict d,
    or None if the dict was invalid.
    """
    d = normalized_cell_dict(d, default_radio=measure_radio)
    d = normalized_measure_dict(d)

    location_is_in_country = geocalc.location_is_in_country
    if d is not None:
        # Lat/lon must be inside one of the bounding boxes for the MCC.
        lat = float(d['lat'])
        lon = float(d['lon'])
        if not any([location_is_in_country(lat, lon, c.alpha2, 1)
                    for c in mobile_codes.mcc(str(d['mcc']))]):
            d = None

    if d is None:
        return None

    if 'asu' in d and 'signal' in d:
        # some clients send us a dBm value in the asu field, move it
        # over to the signal field before hitting validation
        if d['asu'] < -1 and d['signal'] == 0:
            d['signal'] = d['asu']
            d['asu'] = -1

    return normalized_dict(
        d, dict(asu=(0, 31, -1),
                signal=(-200, -1, 0),
                ta=(0, 63, 0)))


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
                 model.lac == k.lac,
                 model.cid == k.cid)
    if isinstance(k, CellKeyPsc) and getattr(model, 'psc', None) is not None:
        # if the model has a psc column, and we get a CellKeyPsc,
        # add it to the criterion
        criterion += (model.psc == k.psc, )
    return criterion


def to_wifikey(obj):
    if isinstance(obj, dict):
        return WifiKey(key=obj['key'])
    elif isinstance(obj, basestring):
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

ocid_cell_table = OCIDCell.__table__


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
        'csv_name': 'wifi_measure.csv',
        'name': 'wifi_measure'},
    2: {'class': CellMeasure,
        'csv_name': 'cell_measure.csv',
        'name': 'cell_measure'},
}
