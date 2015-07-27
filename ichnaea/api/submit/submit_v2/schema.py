import colander

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

    psc = OptionalIntNode(internal_name='primaryScramblingCode')


class CellTowersV2Schema(OptionalSequenceSchema):

    cell = CellTowerV2Schema()


class ReportV2Schema(PositionSchema, ReportSchema):

    _position_fields = (
        'latitude',
        'longitude',
        'accuracy',
        'altitude',
        'altitudeAccuracy',
        'age',
        'heading',
        'pressure',
        'speed',
        'source',
    )

    cellTowers = CellTowersV2Schema(missing=())

    def deserialize(self, data):
        data = super(ReportV2Schema, self).deserialize(data)
        if data in (colander.drop, colander.null):
            return data
        position_data = {}
        for field in self._position_fields:
            if field in data:
                position_data[field] = data[field]
                del data[field]
        if position_data:
            data['position'] = position_data
        return data


class ReportsV2Schema(OptionalSequenceSchema):
    report = ReportV2Schema()


class SubmitV2Schema(OptionalMappingSchema):
    items = ReportsV2Schema()
