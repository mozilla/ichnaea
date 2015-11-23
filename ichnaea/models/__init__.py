"""
Contains SQLAlchemy database models and colander validation schemata.
"""

from ichnaea.models.base import _Model

# import all models, to make sure they are all registered
from ichnaea.models.api import ApiKey  # NOQA
from ichnaea.models.cell import (  # NOQA
    Cell,
    CellArea,
    CellAreaOCID,
    CellBlocklist,
    CellOCID,
    CellShard,
    decode_cellarea,
    decode_cellid,
    encode_cellarea,
    encode_cellid,
    Radio,
)
from ichnaea.models.content import (  # NOQA
    DataMap,
    RegionStat,
    Score,
    ScoreKey,
    Stat,
    StatCounter,
    StatKey,
    User,
)
from ichnaea.models.observation import (  # NOQA
    CellObservation,
    CellReport,
    Report,
    WifiObservation,
    WifiReport,
)
from ichnaea.models.station import StationSource  # NOQA
from ichnaea.models.wifi import (  # NOQA
    decode_mac,
    encode_mac,
    WifiShard,
)

__all__ = (_Model, )
