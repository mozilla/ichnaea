from ichnaea.api.schema import (
    OptionalIntNode,
    OptionalMappingSchema,
    OptionalSequenceSchema,
)
from ichnaea.api.submit.schema import (
    BluetoothBeaconsSchema,
    CellTowerSchema,
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
    position = PositionSchema(missing=None)

    # connection is not mapped on purpose
    # connection = ConnectionSchema(missing=None)


class ReportsV3Schema(OptionalSequenceSchema):

    report = ReportV3Schema()


class SubmitV3Schema(OptionalMappingSchema):

    items = ReportsV3Schema()
