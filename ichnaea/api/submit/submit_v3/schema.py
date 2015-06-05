from ichnaea.api.schema import (
    OptionalIntNode,
    OptionalMappingSchema,
    OptionalSequenceSchema,
)
from ichnaea.api.submit import schema_submit


class CellTowerV3Schema(schema_submit.CellTowerSchema):

    primaryScramblingCode = OptionalIntNode()


class CellTowersV3Schema(OptionalSequenceSchema):

    cell = CellTowerV3Schema()


class ReportV3Schema(schema_submit.ReportSchema):

    bluetoothBeacons = schema_submit.BluetoothBeaconsSchema(missing=())
    cellTowers = CellTowersV3Schema(missing=())
    connection = schema_submit.ConnectionSchema(missing=None)
    position = schema_submit.PositionSchema(missing=None)


class ReportsV3Schema(OptionalSequenceSchema):

    report = ReportV3Schema()


class SubmitV3Schema(OptionalMappingSchema):

    items = ReportsV3Schema()
