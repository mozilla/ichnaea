from ichnaea.api.locate.cell import (
    OCIDCellAreaPositionProvider,
    OCIDCellPositionProvider,
)
from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.source import PositionMultiSource


class OCIDPositionSource(PositionMultiSource):

    fallback_field = None  #:
    source = DataSource.ocid  #:
    provider_classes = (
        OCIDCellAreaPositionProvider,
        OCIDCellPositionProvider,
    )  #:
