import colander

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


class CellTowersV3Schema(OptionalSequenceSchema):

    @colander.instantiate()
    class SequenceItem(CellTowerSchema):

        primaryScramblingCode = OptionalIntNode()


class SubmitV3Schema(OptionalMappingSchema):

    @colander.instantiate()
    class items(OptionalSequenceSchema):  # NOQA

        @colander.instantiate()
        class SequenceItem(ReportSchema):

            bluetoothBeacons = BluetoothBeaconsSchema(missing=())
            cellTowers = CellTowersV3Schema(missing=())
            position = PositionSchema(missing=None)

            # connection is not mapped on purpose
            # connection = ConnectionSchema(missing=None)


SUBMIT_V3_SCHEMA = SubmitV3Schema()
