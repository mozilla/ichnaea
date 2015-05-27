from colander import (
    Integer,
    MappingSchema,
    SchemaNode,
    SequenceSchema,
)

from ichnaea.service import schema_submit


class CellTowerSchema(schema_submit.CellTowerSchema):

    primaryScramblingCode = SchemaNode(Integer(), missing=None)


class CellTowersSchema(SequenceSchema):

    cell = CellTowerSchema()


class ReportSchema(schema_submit.ReportSchema):

    bluetoothBeacons = schema_submit.BluetoothBeaconsSchema(missing=())
    cellTowers = CellTowersSchema(missing=())
    connection = schema_submit.ConnectionSchema(missing=None)
    position = schema_submit.PositionSchema(missing=None)


class ReportsSchema(SequenceSchema):

    report = ReportSchema()


class GeoSubmit2Schema(MappingSchema):

    items = ReportsSchema()
