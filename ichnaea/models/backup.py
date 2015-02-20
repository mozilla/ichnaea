from enum import IntEnum
from sqlalchemy import (
    BINARY,
    Column,
    Index,
    String,
)
from sqlalchemy.dialects.mysql import BIGINT as BigInteger

from ichnaea.models.base import (
    _Model,
    BigIdMixin,
)
from ichnaea.models.observation import (
    CellObservation,
    WifiObservation,
)
from ichnaea.models.sa_types import (
    TinyIntEnum,
    TZDateTime as DateTime,
)


class ObservationType(IntEnum):
    wifi = 1
    cell = 2


OBSERVATION_TYPE_META = {
    ObservationType.wifi: {
        'class': WifiObservation,
        'csv_name': 'wifi_measure.csv'},
    ObservationType.cell: {
        'class': CellObservation,
        'csv_name': 'cell_measure.csv'},
}


class ObservationBlock(BigIdMixin, _Model):
    __tablename__ = 'measure_block'

    _indices = (
        Index('idx_measure_block_archive_date', 'archive_date'),
        Index('idx_measure_block_s3_key', 's3_key'),
        Index('idx_measure_block_end_id', 'end_id'),
    )
    _settings = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        'mysql_row_format': 'compressed',
        'mysql_key_block_size': '4',
    }

    measure_type = Column(TinyIntEnum(ObservationType))
    s3_key = Column(String(80))
    archive_date = Column(DateTime)
    archive_sha = Column(BINARY(length=20))
    start_id = Column(BigInteger(unsigned=True))
    end_id = Column(BigInteger(unsigned=True))
