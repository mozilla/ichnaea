from ichnaea.service.schema import (
    OptionalIntNode,
    OptionalMappingSchema,
    OptionalSequenceSchema,
)
from ichnaea.service import schema_submit


class CellTowerSchema(schema_submit.CellTowerSchema):

    psc = OptionalIntNode()


class CellTowersSchema(OptionalSequenceSchema):

    cell = CellTowerSchema()


class ReportSchema(schema_submit.PositionSchema, schema_submit.ReportSchema):

    cellTowers = CellTowersSchema(missing=())


class ReportsSchema(OptionalSequenceSchema):
    report = ReportSchema()


class GeoSubmitSchema(OptionalMappingSchema):
    items = ReportsSchema()
