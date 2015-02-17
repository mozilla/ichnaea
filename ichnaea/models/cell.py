from collections import namedtuple

from sqlalchemy import (
    Column,
    Index,
    Boolean,
)
from sqlalchemy.dialects.mysql import (
    DOUBLE as Double,
    INTEGER as Integer,
    SMALLINT as SmallInteger,
    TINYINT as TinyInteger,
)

from ichnaea import geocalc
from ichnaea.models.base import _Model
from ichnaea.models.sa_types import TZDateTime as DateTime
from ichnaea import util

CellKey = namedtuple('CellKey', 'radio mcc mnc lac cid')
CellKeyPsc = namedtuple('CellKey', 'radio mcc mnc lac cid psc')
CellAreaKey = namedtuple('CellAreaKey', 'radio mcc mnc lac')


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


class Cell(_Model):
    __tablename__ = 'cell'
    __table_args__ = (
        Index('cell_created_idx', 'created'),
        Index('cell_modified_idx', 'modified'),
        Index('cell_new_measures_idx', 'new_measures'),
        Index('cell_total_measures_idx', 'total_measures'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
        }
    )

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
    radio = Column(TinyInteger, autoincrement=False, primary_key=True)
    # int in the range 0-1000
    mcc = Column(SmallInteger, autoincrement=False, primary_key=True)
    # int in the range 0-1000 for gsm
    # int in the range 0-32767 for cdma (system id)
    mnc = Column(SmallInteger, autoincrement=False, primary_key=True)
    lac = Column(
        SmallInteger(unsigned=True), autoincrement=False, primary_key=True)
    cid = Column(Integer(unsigned=True), autoincrement=False, primary_key=True)
    psc = Column(SmallInteger)
    range = Column(Integer)
    new_measures = Column(Integer(unsigned=True))
    total_measures = Column(Integer(unsigned=True))

    def __init__(self, *args, **kw):
        if 'created' not in kw:
            kw['created'] = util.utcnow()
        if 'modified' not in kw:
            kw['modified'] = util.utcnow()
        if 'lac' not in kw or not kw['lac']:
            kw['lac'] = 0
        if 'cid' not in kw or not kw['cid']:
            kw['cid'] = 0
        if 'range' not in kw:
            kw['range'] = 0
        if 'new_measures' not in kw:
            kw['new_measures'] = 0
        if 'total_measures' not in kw:
            kw['total_measures'] = 0
        super(Cell, self).__init__(*args, **kw)


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
        if 'lac' not in kw or not kw['lac']:
            kw['lac'] = 0
        if 'cid' not in kw or not kw['cid']:
            kw['cid'] = 0
        if 'range' not in kw:
            kw['range'] = 0
        if 'total_measures' not in kw:
            kw['total_measures'] = 0
        if 'changeable' not in kw:
            kw['changeable'] = True
        super(OCIDCell, self).__init__(*args, **kw)

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


class CellBlacklist(_Model):
    __tablename__ = 'cell_blacklist'
    __table_args__ = ({
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
    })
    time = Column(DateTime)
    radio = Column(TinyInteger, autoincrement=False, primary_key=True)
    mcc = Column(SmallInteger, autoincrement=False, primary_key=True)
    mnc = Column(SmallInteger, autoincrement=False, primary_key=True)
    lac = Column(
        SmallInteger(unsigned=True), autoincrement=False, primary_key=True)
    cid = Column(Integer(unsigned=True), autoincrement=False, primary_key=True)
    count = Column(Integer)

    def __init__(self, *args, **kw):
        if 'time' not in kw:
            kw['time'] = util.utcnow()
        if 'count' not in kw:
            kw['count'] = 1
        super(CellBlacklist, self).__init__(*args, **kw)


CELL_MODEL_KEYS = {
    'cell': Cell,
    'cell_area': CellArea,
    'ocid_cell': OCIDCell,
    'ocid_cell_area': OCIDCellArea,
}
