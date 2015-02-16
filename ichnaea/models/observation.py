from sqlalchemy import (
    BINARY,
    Column,
    Float,
    Index,
    String,
)
from sqlalchemy.dialects.mysql import (
    BIGINT as BigInteger,
    DOUBLE as Double,
    INTEGER as Integer,
    SMALLINT as SmallInteger,
    TINYINT as TinyInteger,
)

from ichnaea.models.base import _Model
from ichnaea.models.sa_types import TZDateTime as DateTime
from ichnaea import util

MEASURE_TYPE_CODE = {
    'wifi': 1,
    'cell': 2,
}
MEASURE_TYPE_CODE_INVERSE = dict((v, k) for k, v in MEASURE_TYPE_CODE.items())


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
    lac = Column(SmallInteger(unsigned=True))
    cid = Column(Integer(unsigned=True))
    psc = Column(SmallInteger)
    asu = Column(SmallInteger)
    signal = Column(SmallInteger)
    ta = Column(TinyInteger)

    def __init__(self, *args, **kw):
        if 'created' not in kw:
            kw['created'] = util.utcnow()
        super(CellMeasure, self).__init__(*args, **kw)

cell_measure_table = CellMeasure.__table__


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

# Keep at end of file, as it needs to stay below the *Measure models
MEASURE_TYPE_META = {
    1: {'class': WifiMeasure,
        'csv_name': 'wifi_measure.csv'},
    2: {'class': CellMeasure,
        'csv_name': 'cell_measure.csv'},
}
