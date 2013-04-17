from sqlalchemy import create_engine
from sqlalchemy import Date, Column, Integer, REAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

_Model = declarative_base()


class Cell(_Model):
    __tablename__ = 'cell'

    id = Column(Integer, primary_key=True)
    lat = Column(REAL)
    lon = Column(REAL)
    mcc = Column(Integer)
    mnc = Column(Integer)
    lac = Column(Integer)
    cid = Column(Integer)
    range = Column(Integer)
    samples = Column(Integer)
    created_at = Column(Date)
    updated_at = Column(Date)
    zero = Column(Integer)

cell_table = Cell.__table__


class Database(object):

    def __init__(self, sqluri):
        self.engine = create_engine(sqluri)
        self.session_factory = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False)

        cell_table.metadata.bind = self.engine
        cell_table.create(checkfirst=True)

    def session(self):
        return self.session_factory()
