from sqlalchemy import create_engine
from sqlalchemy import Column, Index
from sqlalchemy import DateTime, Integer, LargeBinary, SmallInteger, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

_Model = declarative_base()


RADIO_TYPE = {
    'gsm': 0,
    'cdma': 1,
    'umts': 2,
    'lte': 3,
}
RADIO_TYPE_KEYS = list(RADIO_TYPE.keys())


class Cell(_Model):
    __tablename__ = 'cell'
    __table_args__ = (
        Index('cell_idx', 'radio', 'mcc', 'mnc', 'lac', 'cid'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
        }
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    # lat/lon * decimaljson.FACTOR
    lat = Column(Integer)
    lon = Column(Integer)
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

cell_table = Cell.__table__


class CellMeasure(_Model):
    __tablename__ = 'cell_measure'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        'mysql_row_format': 'compressed',
        'mysql_key_block_size': '4',
    }

    id = Column(Integer, primary_key=True, autoincrement=True)

cell_measure_table = CellMeasure.__table__


class Wifi(_Model):
    __tablename__ = 'wifi'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
    }

    key = Column(String(40), primary_key=True)
    # lat/lon * decimaljson.FACTOR
    lat = Column(Integer)
    lon = Column(Integer)
    range = Column(Integer)

wifi_table = Wifi.__table__


class WifiMeasure(_Model):
    __tablename__ = 'wifi_measure'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        'mysql_row_format': 'compressed',
        'mysql_key_block_size': '4',
    }

    id = Column(Integer, primary_key=True, autoincrement=True)

wifi_measure_table = WifiMeasure.__table__


class Measure(_Model):
    __tablename__ = 'measure'
    __table_args__ = (
        Index('measure_time_idx', 'time'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
            'mysql_row_format': 'compressed',
            'mysql_key_block_size': '4',
        }
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    # lat/lon * decimaljson.FACTOR
    lat = Column(Integer)
    lon = Column(Integer)
    time = Column(DateTime)
    accuracy = Column(Integer)
    altitude = Column(Integer)
    altitude_accuracy = Column(Integer)
    radio = Column(SmallInteger)  # mapped via RADIO_TYPE
    # json blobs
    cell = Column(LargeBinary)
    wifi = Column(LargeBinary)

measure_table = Measure.__table__


class Score(_Model):
    __tablename__ = 'score'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
    }

    id = Column(Integer, primary_key=True, autoincrement=True)
    userid = Column(Integer, index=True, unique=True)
    value = Column(Integer)

score_table = Score.__table__


class User(_Model):
    __tablename__ = 'user'
    __table_args__ = (
        Index('user_token_idx', 'token'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
        }
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(36))
    nickname = Column(String(128))

user_table = User.__table__


class Database(object):

    def __init__(self, sqluri):
        options = dict(pool_recycle=3600, pool_size=10, pool_timeout=10)
        if sqluri.startswith('sqlite'):
            del options['pool_size']
            del options['pool_timeout']
        self.engine = create_engine(sqluri, **options)
        self.session_factory = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False)

        # bind and create tables
        for table in (cell_table, cell_measure_table,
                      wifi_table, wifi_measure_table,
                      measure_table, user_table, score_table):
            table.metadata.bind = self.engine
            table.create(checkfirst=True)

    def session(self):
        return self.session_factory()
