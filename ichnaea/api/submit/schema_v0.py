"""
Colander schemata describing the public v1/submit HTTP API.
"""

import colander

from ichnaea.api.schema import (
    OptionalBoundedFloatNode,
    OptionalIntNode,
    OptionalMappingSchema,
    OptionalNode,
    OptionalSequenceSchema,
    OptionalStringNode,
    UnixTimeFromString,
)


class CellV0Schema(OptionalMappingSchema):

    radio = OptionalStringNode(internal_name='radioType')
    mcc = OptionalIntNode(internal_name='mobileCountryCode')
    mnc = OptionalIntNode(internal_name='mobileNetworkCode')
    lac = OptionalIntNode(internal_name='locationAreaCode')
    cid = OptionalIntNode(internal_name='cellId')

    age = OptionalIntNode()
    asu = OptionalIntNode()
    psc = OptionalIntNode(internal_name='primaryScramblingCode')
    serving = OptionalIntNode()
    signal = OptionalIntNode(internal_name='signalStrength')
    ta = OptionalIntNode(internal_name='timingAdvance')


class WifiV0Schema(OptionalMappingSchema):

    key = OptionalStringNode(internal_name='macAddress')

    age = OptionalIntNode()
    channel = OptionalIntNode()
    frequency = OptionalIntNode()
    radio = OptionalStringNode(internal_name='radioType')
    signal = OptionalIntNode(internal_name='signalStrength')
    signalToNoiseRatio = OptionalIntNode()
    ssid = OptionalStringNode()

    def deserialize(self, data):
        data = super(WifiV0Schema, self).deserialize(data)
        if 'macAddress' not in data:
            return colander.null
        return data


class BaseReportV0Schema(OptionalMappingSchema):

    lat = OptionalBoundedFloatNode(internal_name='latitude')
    lon = OptionalBoundedFloatNode(internal_name='longitude')

    time = OptionalNode(UnixTimeFromString(), internal_name='timestamp')
    accuracy = OptionalBoundedFloatNode()
    age = OptionalIntNode()
    altitude = OptionalBoundedFloatNode()
    altitude_accuracy = OptionalBoundedFloatNode(
        internal_name='altitudeAccuracy')
    heading = OptionalBoundedFloatNode()
    pressure = OptionalBoundedFloatNode()
    radio = OptionalStringNode(internal_name='radioType')
    speed = OptionalBoundedFloatNode()
    source = OptionalStringNode()


class ReportV0Schema(BaseReportV0Schema):

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

    @colander.instantiate(internal_name='cellTowers', missing=())
    class cell(OptionalSequenceSchema):  # NOQA
        sequence_item = CellV0Schema()

    @colander.instantiate(internal_name='wifiAccessPoints', missing=())
    class wifi(OptionalSequenceSchema):  # NOQA
        sequence_item = WifiV0Schema()

    def deserialize(self, data):
        data = super(ReportV0Schema, self).deserialize(data)
        if data in (colander.drop, colander.null):  # pragma: no cover
            return data

        if not (data.get('cellTowers') or data.get('wifiAccessPoints')):
            return colander.null

        top_radio = data.get('radioType', None)
        for cell in data.get('cellTowers', ()):
            if 'radioType' not in cell or not cell['radioType'] and top_radio:
                cell['radioType'] = top_radio
            if cell.get('radioType') == 'umts':
                cell['radioType'] = 'wcdma'

        if 'radioType' in data:
            del data['radioType']

        position_data = {}
        for field in self._position_fields:
            if field in data:
                position_data[field] = data[field]
                del data[field]
        if position_data:
            data['position'] = position_data

        return data


class SubmitV0Schema(OptionalMappingSchema):

    @colander.instantiate()
    class items(OptionalSequenceSchema):  # NOQA

        report = ReportV0Schema()


SUBMIT_V0_SCHEMA = SubmitV0Schema()
