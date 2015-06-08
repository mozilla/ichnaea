from ichnaea.api.schema import (
    OptionalIntNode,
    OptionalMappingSchema,
    OptionalSequenceSchema,
)
from ichnaea.api.submit.schema import (
    CellTowerSchema,
    PositionSchema,
    ReportSchema,
)


class CellTowerV2Schema(CellTowerSchema):

    psc = OptionalIntNode()


class CellTowersV2Schema(OptionalSequenceSchema):

    cell = CellTowerV2Schema()


class ReportV2Schema(PositionSchema, ReportSchema):

    cellTowers = CellTowersV2Schema(missing=())


class ReportsV2Schema(OptionalSequenceSchema):
    report = ReportV2Schema()


class SubmitV2Schema(OptionalMappingSchema):
    items = ReportsV2Schema()
