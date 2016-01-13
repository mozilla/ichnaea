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

    @colander.instantiate(missing=())
    class cellTowers(OptionalSequenceSchema):  # NOQA

        @colander.instantiate()
        class SequenceItem(CellTowerSchema):

            psc = OptionalIntNode(internal_name='primaryScramblingCode')

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


class SubmitV2Schema(OptionalMappingSchema):

    @colander.instantiate()
    class items(OptionalSequenceSchema):  # NOQA
        report = ReportV2Schema()


SUBMIT_V2_SCHEMA = SubmitV2Schema()
