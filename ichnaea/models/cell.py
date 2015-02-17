from collections import namedtuple

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
    PositionMixin,
    TimeTrackingMixin,
)
from ichnaea.models.station import (
    BaseStationMixin,
    StationMixin,
    StationBlacklistMixin,
)

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


class CellAreaKeyMixin(object):

    # mapped via RADIO_TYPE
    radio = Column(TinyInteger, autoincrement=False)
    mcc = Column(SmallInteger, autoincrement=False)
    mnc = Column(SmallInteger, autoincrement=False)
    lac = Column(SmallInteger(unsigned=True), autoincrement=False)


class CellAreaMixin(CellAreaKeyMixin, TimeTrackingMixin, PositionMixin):

    range = Column(Integer)
    avg_cell_range = Column(Integer)
    num_cells = Column(Integer(unsigned=True))


class CellKeyMixin(CellAreaKeyMixin):

    cid = Column(Integer(unsigned=True), autoincrement=False)


class CellKeyPscMixin(CellKeyMixin):

    psc = Column(SmallInteger, autoincrement=False)


class CellMixin(CellKeyPscMixin):
    pass


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


class OCIDCell(CellMixin, BaseStationMixin, _Model):
    __tablename__ = 'ocid_cell'

    _indices = (
        PrimaryKeyConstraint('radio', 'mcc', 'mnc', 'lac', 'cid'),
        Index('ocid_cell_created_idx', 'created'),
    )

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


CELL_MODEL_KEYS = {
    'cell': Cell,
    'cell_area': CellArea,
    'ocid_cell': OCIDCell,
    'ocid_cell_area': OCIDCellArea,
}
