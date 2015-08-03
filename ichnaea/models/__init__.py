"""
Contains SQLAlchemy database models and colander validation schemata.
"""

from ichnaea.models.base import _Model

# import all models, to make sure they are all registered
from ichnaea.models.api import ApiKey  # NOQA
from ichnaea.models.cell import (  # NOQA
    Cell,
    CellArea,
    CellBlocklist,
    OCIDCell,
    OCIDCellArea,
    Radio,
)
from ichnaea.models.content import (  # NOQA
    MapStat,
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
from ichnaea.models.wifi import (  # NOQA
    Wifi,
    WifiShard,
)

__all__ = (_Model, )
