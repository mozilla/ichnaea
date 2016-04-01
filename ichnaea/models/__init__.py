"""
Contains SQLAlchemy database models and colander validation schemata.
"""

from ichnaea.models.base import _Model

# import all models, to make sure they are all registered
from ichnaea.models.constants import Radio  # NOQA
from ichnaea.models.api import ApiKey  # NOQA
from ichnaea.models.blue import (  # NOQA
    BlueShard,
)
from ichnaea.models.cell import (  # NOQA
    CellArea,
    CellAreaOCID,
    CellOCID,
    CellShard,
    CellShardOCID,
    decode_cellarea,
    decode_cellid,
    encode_cellarea,
    encode_cellid,
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
from ichnaea.models.mac import (  # NOQA
    decode_mac,
    encode_mac,
)
from ichnaea.models.observation import (  # NOQA
    BlueObservation,
    BlueReport,
    CellObservation,
    CellReport,
    Report,
    WifiObservation,
    WifiReport,
)
from ichnaea.models.station import StationSource  # NOQA
from ichnaea.models.wifi import (  # NOQA
    WifiShard,
)

__all__ = (_Model, )
