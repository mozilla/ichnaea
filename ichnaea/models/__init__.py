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
    CellKey,
    CellKeyMixin,
    CellKeyPsc,
    CellKeyPscMixin,
    CELL_MODEL_KEYS,
    OCIDCell,
    OCIDCellArea,
    RADIO_TYPE,
    RADIO_TYPE_KEYS,
    RADIO_TYPE_INVERSE,
    MAX_RADIO_TYPE,
    MIN_RADIO_TYPE,
)
from ichnaea.models.content import (  # NOQA
    MapStat,
    Score,
    ScoreKey,
    Stat,
    StatKey,
    User,
)
from ichnaea.models.observation import (  # NOQA
    CellObservation,
    ReportMixin,
    WifiObservation,
)
from ichnaea.models.wifi import (  # NOQA
    Wifi,
    WifiBlacklist,
    WifiKey,
    WifiKeyMixin,
)

__all__ = (_Model, )
