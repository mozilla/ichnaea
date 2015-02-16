from enum import IntEnum
from sqlalchemy import (
    BINARY,
    Column,
    Index,
    String,
)
from sqlalchemy.dialects.mysql import BIGINT as BigInteger

from ichnaea.models.base import _Model
from ichnaea.models.observation import (
    CellMeasure,
    WifiMeasure,
)
from ichnaea.models.sa_types import (
    TinyIntEnum,
    TZDateTime as DateTime,
)


class MeasureType(IntEnum):
    wifi = 1
    cell = 2


MEASURE_TYPE_META = {
    MeasureType.wifi: {
        'class': WifiMeasure,
        'csv_name': 'wifi_measure.csv'},
    MeasureType.cell: {
        'class': CellMeasure,
        'csv_name': 'cell_measure.csv'},
}


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
    measure_type = Column(TinyIntEnum(MeasureType))
    s3_key = Column(String(80))
    archive_date = Column(DateTime)
    archive_sha = Column(BINARY(length=20))
    start_id = Column(BigInteger(unsigned=True))
    end_id = Column(BigInteger(unsigned=True))
