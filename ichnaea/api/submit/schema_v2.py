"""
Colander schemata describing the public v2/geosubmit HTTP API.
"""

import colander

from ichnaea.api.schema import (
    OptionalIntNode,
    OptionalMappingSchema,
    OptionalSequenceSchema,
)
from ichnaea.api.submit.schema import CellTowerSchema, PositionSchema, ReportSchema


class CellTowersV2Schema(OptionalSequenceSchema):
    @colander.instantiate()
    class SequenceItem(CellTowerSchema):

        primaryScramblingCode = OptionalIntNode()


class SubmitV2Schema(OptionalMappingSchema):
    @colander.instantiate()
    class items(OptionalSequenceSchema):
        @colander.instantiate()
        class SequenceItem(ReportSchema):

            cellTowers = CellTowersV2Schema(missing=())
            position = PositionSchema(missing=colander.drop)


SUBMIT_V2_SCHEMA = SubmitV2Schema()
