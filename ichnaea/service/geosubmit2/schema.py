from ichnaea.service.schema import (
    OptionalIntNode,
    OptionalMappingSchema,
    OptionalSequenceSchema,
)
from ichnaea.service import schema_submit


class CellTowerSchema(schema_submit.CellTowerSchema):

    primaryScramblingCode = OptionalIntNode()


class CellTowersSchema(OptionalSequenceSchema):

    cell = CellTowerSchema()


class ReportSchema(schema_submit.ReportSchema):

    bluetoothBeacons = schema_submit.BluetoothBeaconsSchema(missing=())
    cellTowers = CellTowersSchema(missing=())
    connection = schema_submit.ConnectionSchema(missing=None)
    position = schema_submit.PositionSchema(missing=None)


class ReportsSchema(OptionalSequenceSchema):

    report = ReportSchema()


class GeoSubmit2Schema(OptionalMappingSchema):

    items = ReportsSchema()
