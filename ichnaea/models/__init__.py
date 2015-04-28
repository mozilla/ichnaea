from ichnaea.models.base import _Model

# import all models, to make sure they are all registered
from ichnaea.models.api import ApiKey  # NOQA
from ichnaea.models.backup import (  # NOQA
    ObservationBlock,
    ObservationType,
    OBSERVATION_TYPE_META,
)
from ichnaea.models.cell import (  # NOQA
    Cell,
    CellArea,
    CellBlacklist,
    OCIDCell,
    OCIDCellArea,
    Radio,
    ValidCellKeySchema,
)
from ichnaea.models.content import (  # NOQA
    MapStat,
    Score,
    ScoreKey,
    Stat,
    statcounter_emit,
    statcounter_key,
    StatKey,
    User,
)
from ichnaea.models.observation import (  # NOQA
    CellLookup,
    CellObservation,
    CellReport,
    Report,
    WifiLookup,
    WifiObservation,
    WifiReport,
)
from ichnaea.models.wifi import (  # NOQA
    Wifi,
    WifiBlacklist,
)

__all__ = (_Model, )
