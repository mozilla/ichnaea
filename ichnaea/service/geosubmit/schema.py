from colander import (
    Integer,
    MappingSchema,
    SchemaNode,
    SequenceSchema,
)

from ichnaea.service import schema_submit


class CellTowerSchema(schema_submit.CellTowerSchema):

    psc = SchemaNode(Integer(), missing=None)


class CellTowersSchema(SequenceSchema):

    cell = CellTowerSchema()


class ReportSchema(schema_submit.PositionSchema, schema_submit.ReportSchema):

    cellTowers = CellTowersSchema(missing=())


class ReportsSchema(SequenceSchema):
    report = ReportSchema()


class GeoSubmitSchema(MappingSchema):
    items = ReportsSchema()
