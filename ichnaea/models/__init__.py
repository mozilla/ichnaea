from ichnaea.models.base import _Model

# import all models, to make sure they are all registered
from ichnaea.models.api import *  # NOQA
from ichnaea.models.backup import *  # NOQA
from ichnaea.models.cell import *  # NOQA
from ichnaea.models.content import *  # NOQA
from ichnaea.models.constants import *  # NOQA
from ichnaea.models.observation import *  # NOQA
from ichnaea.models.wifi import *  # NOQA

__all__ = (_Model, )
