from sqlalchemy import create_engine
from sqlalchemy import Column, Index, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

_Model = declarative_base()


class Cell(_Model):
    __tablename__ = 'cell'
    __table_args__ = (
        Index('cell_idx', 'mcc', 'mnc', 'lac', 'cid'),
    )

    id = Column(Integer, primary_key=True)
    # lat/lon * 1000000
    lat = Column(Integer)
    lon = Column(Integer)

    mcc = Column(Integer)
    mnc = Column(Integer)
    lac = Column(Integer)
    cid = Column(Integer)
    range = Column(Integer)

cell_table = Cell.__table__


class Measure(_Model):
    __tablename__ = 'measure'

    id = Column(Integer, primary_key=True)

measure_table = Measure.__table__


class BaseDB(object):

    def __init__(self, sqluri):
        self.engine = create_engine(sqluri)
        self.session_factory = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False)

    def session(self):
        return self.session_factory()


class CellDB(BaseDB):

    def __init__(self, sqluri):
        super(CellDB, self).__init__(sqluri)
        cell_table.metadata.bind = self.engine
        cell_table.create(checkfirst=True)


class MeasureDB(BaseDB):

    def __init__(self, sqluri):
        super(MeasureDB, self).__init__(sqluri)
        measure_table.metadata.bind = self.engine
        measure_table.create(checkfirst=True)
