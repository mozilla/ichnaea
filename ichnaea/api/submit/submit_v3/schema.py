from ichnaea.api.schema import (
    OptionalIntNode,
    OptionalMappingSchema,
    OptionalSequenceSchema,
)
from ichnaea.api.submit.schema import (
    BluetoothBeaconsSchema,
    CellTowerSchema,
    ConnectionSchema,
    PositionSchema,
    ReportSchema,
)


class CellTowerV3Schema(CellTowerSchema):

    primaryScramblingCode = OptionalIntNode()


class CellTowersV3Schema(OptionalSequenceSchema):

    cell = CellTowerV3Schema()


class ReportV3Schema(ReportSchema):

    bluetoothBeacons = BluetoothBeaconsSchema(missing=())
    cellTowers = CellTowersV3Schema(missing=())
    connection = ConnectionSchema(missing=None)
    position = PositionSchema(missing=None)


class ReportsV3Schema(OptionalSequenceSchema):

    report = ReportV3Schema()


class SubmitV3Schema(OptionalMappingSchema):

    items = ReportsV3Schema()
