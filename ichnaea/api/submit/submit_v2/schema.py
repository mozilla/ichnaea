from ichnaea.api.schema import (
    OptionalIntNode,
    OptionalMappingSchema,
    OptionalSequenceSchema,
)
from ichnaea.api.submit import schema_submit


class CellTowerV2Schema(schema_submit.CellTowerSchema):

    psc = OptionalIntNode()


class CellTowersV2Schema(OptionalSequenceSchema):

    cell = CellTowerV2Schema()


class ReportV2Schema(schema_submit.PositionSchema, schema_submit.ReportSchema):

    cellTowers = CellTowersV2Schema(missing=())


class ReportsV2Schema(OptionalSequenceSchema):
    report = ReportV2Schema()


class SubmitV2Schema(OptionalMappingSchema):
    items = ReportsV2Schema()
