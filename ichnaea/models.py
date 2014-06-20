from collections import namedtuple
from datetime import date, datetime
from colander import iso8601
import ichnaea.geocalc
import mobile_codes
import re

from sqlalchemy import (
    BINARY,
    Column,
    DateTime,
    Float,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import INTEGER as Integer
from sqlalchemy.dialects.mysql import BIGINT as BigInteger

from ichnaea.db import _Model

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

# Accuracy on land is arbitrarily bounded to [0, 1000km],
# past which it seems more likely we're looking at bad data.
MAX_ACCURACY = 1000000

# Challenger Deep, Mariana Trench.
MIN_ALTITUDE = -10911

# Karman Line, edge of space.
MAX_ALTITUDE = 100000

MAX_ALTITUDE_ACCURACY = abs(MAX_ALTITUDE - MIN_ALTITUDE)

MAX_HEADING = 360.0

# A bit less than speed of sound, in meters per second
MAX_SPEED = 300.0

# Empirical 95th percentile accuracy of ichnaea's responses,
# from feedback testing of measurements as queries.
WIFI_MIN_ACCURACY = 100
CELL_MIN_ACCURACY = 5000
LAC_MIN_ACCURACY = 20000

# Pure guesswork, "size of a city"
GEOIP_CITY_ACCURACY = 50000

# Numeric constant used to indicate "virtual cells" for LACs, in db.
CELLID_LAC = -2

# Symbolic constant used in specs passed to normalization functions.
REQUIRED = object()

# We use a documentation-only multi-cast address as a test key
# http://tools.ietf.org/html/rfc7042#section-2.1.1
WIFI_TEST_KEY = "01005e901000"
INVALID_WIFI_REGEX = re.compile("(?!(0{12}|f{12}|%s))" % WIFI_TEST_KEY)
VALID_WIFI_REGEX = re.compile("([0-9a-fA-F]{12})")

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


def from_degrees(deg):
    return int(deg * DEGREE_SCALE_FACTOR)


def to_degrees(i):
    return float(i) / DEGREE_SCALE_FACTOR


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
        return datetime.utcnow().replace(tzinfo=iso8601.UTC)


def valid_wifi_pattern(key):
    return INVALID_WIFI_REGEX.match(key) and \
        VALID_WIFI_REGEX.match(key) and len(key) == 12


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
        d, dict(lat=(from_degrees(-90.0), from_degrees(90.0), REQUIRED),
                lon=(from_degrees(-180.0), from_degrees(180.0), REQUIRED),
                heading=(0.0, MAX_HEADING, -1.0),
                speed=(0, MAX_SPEED, -1.0),
                altitude=(MIN_ALTITUDE, MAX_ALTITUDE, 0),
                altitude_accuracy=(0, MAX_ALTITUDE_ACCURACY, 0),
                accuracy=(0, MAX_ACCURACY, 0)))

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
                lac=(0, 65535, -1),
                cid=(0, 268435455, -1),
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

    # Treat the lac=0, cid=65535 combination as unspecified values
    if d['lac'] == 0 and d['cid'] == 65535:
        d['lac'] = -1
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

    location_is_in_country = ichnaea.geocalc.location_is_in_country
    if d is not None:
        # Lat/lon must be inside one of the bounding boxes for the MCC.
        lat = to_degrees(int(d['lat']))
        lon = to_degrees(int(d['lon']))
        if not any([location_is_in_country(lat, lon, c.alpha2, 1)
                    for c in mobile_codes.mcc(str(d['mcc']))]):
            d = None

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
            kw['created'] = datetime.utcnow()
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
    created = Column(DateTime)
    radio = Column(SmallInteger)
    mcc = Column(SmallInteger)
    mnc = Column(Integer)
    lac = Column(Integer)
    cid = Column(Integer)

    def __init__(self, *args, **kw):
        if 'created' not in kw:
            kw['created'] = datetime.utcnow()
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
    measure_id = Column(BigInteger(unsigned=True))
    created = Column(DateTime)  # the insert time of the record into the DB
    # lat/lon * DEGREE_SCALE_FACTOR
    lat = Column(Integer)
    lon = Column(Integer)
    time = Column(DateTime)  # the time of observation of this data
    accuracy = Column(Integer)
    altitude = Column(Integer)
    altitude_accuracy = Column(Integer)

    # http://dev.w3.org/geo/api/spec-source.html#heading
    heading = Column(Float)

    # http://dev.w3.org/geo/api/spec-source.html#speed
    speed = Column(Float)

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
            kw['created'] = datetime.utcnow()
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
            kw['created'] = datetime.utcnow()
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
    created = Column(DateTime)
    key = Column(String(12))

    def __init__(self, *args, **kw):
        if 'created' not in kw:
            kw['created'] = datetime.utcnow()
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
    measure_id = Column(BigInteger(unsigned=True))
    created = Column(DateTime)  # the insert time of the record into the DB
    # lat/lon * DEGREE_SCALE_FACTOR
    lat = Column(Integer)
    lon = Column(Integer)
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
        if 'measure_id' not in kw:
            kw['measure_id'] = 0
        if 'created' not in kw:
            kw['created'] = datetime.utcnow()
        super(WifiMeasure, self).__init__(*args, **kw)

wifi_measure_table = WifiMeasure.__table__


class Measure(_Model):
    __tablename__ = 'measure'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
    }

    id = Column(BigInteger(unsigned=True),
                primary_key=True, autoincrement=True)

measure_table = Measure.__table__


class ApiKey(_Model):
    __tablename__ = 'api_key'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
    }

    valid_key = Column(String(40),
                       primary_key=True)

    # Maximum number of requests per day
    maxreq = Column(Integer, default=0)

api_key_table = ApiKey.__table__


MEASURE_TYPE_CODE = {
    'wifi': 1,
    'cell': 2,
}
MEASURE_TYPE_CODE_INVERSE = dict((v, k) for k, v in MEASURE_TYPE_CODE.items())

MEASURE_TYPE_META = {
    1: {'class': WifiMeasure,
        'csv_name': 'wifi_measure.csv'},
    2: {'class': CellMeasure,
        'csv_name': 'cell_measure.csv'},
}
