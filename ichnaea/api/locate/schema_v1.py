"""
Colander schemata describing the public v1/geolocate HTTP API.

This API is based on the `Google geolocation API
<https://developers.google.com/maps/documentation/business/geolocation/>`_.
"""

import colander

from ichnaea.api.schema import RenamingMappingSchema
from ichnaea.api.locate.schema import (
    BaseLocateSchema,
    FallbackSchema,
)

RADIO_STRINGS = ['gsm', 'cdma', 'wcdma', 'lte']


class BluetoothBeaconsSchema(colander.SequenceSchema):

    @colander.instantiate()
    class SequenceItem(RenamingMappingSchema):

        macAddress = colander.SchemaNode(
            colander.String(), missing=None, to_name='mac')
        age = colander.SchemaNode(colander.Integer(), missing=None)
        signalStrength = colander.SchemaNode(
            colander.Integer(), missing=None, to_name='signal')
        name = colander.SchemaNode(colander.String(), missing=None)


class CellTowersSchema(colander.SequenceSchema):

    @colander.instantiate()
    class SequenceItem(RenamingMappingSchema):

        # radio is a FxOS specific undocumented workaround
        radio = colander.SchemaNode(
            colander.String(),
            validator=colander.OneOf(RADIO_STRINGS), missing=colander.drop)
        # radioType resolves to the internal field 'radio', so if both
        # 'radio' and 'radioType' are provided, radioType should take
        # precedence. colander respects the order that fields are defined
        # and so radioType is defined after the 'radio' field.
        radioType = colander.SchemaNode(
            colander.String(), validator=colander.OneOf(RADIO_STRINGS),
            missing=colander.drop, to_name='radio')
        mobileCountryCode = colander.SchemaNode(
            colander.Integer(), missing=None, to_name='mcc')
        mobileNetworkCode = colander.SchemaNode(
            colander.Integer(), missing=None, to_name='mnc')
        locationAreaCode = colander.SchemaNode(
            colander.Integer(), missing=None, to_name='lac')
        cellId = colander.SchemaNode(
            colander.Integer(), missing=None, to_name='cid')

        age = colander.SchemaNode(colander.Integer(), missing=None)
        psc = colander.SchemaNode(colander.Integer(), missing=None)
        signalStrength = colander.SchemaNode(
            colander.Integer(), missing=None, to_name='signal')
        timingAdvance = colander.SchemaNode(
            colander.Integer(), missing=None, to_name='ta')


class WifiAccessPointsSchema(colander.SequenceSchema):

    @colander.instantiate()
    class SequenceItem(RenamingMappingSchema):

        macAddress = colander.SchemaNode(
            colander.String(), missing=None, to_name='mac')
        age = colander.SchemaNode(colander.Integer(), missing=None)
        channel = colander.SchemaNode(colander.Integer(), missing=None)
        frequency = colander.SchemaNode(colander.Integer(), missing=None)
        signalStrength = colander.SchemaNode(
            colander.Integer(), missing=None, to_name='signal')
        signalToNoiseRatio = colander.SchemaNode(
            colander.Integer(), missing=None, to_name='snr')
        ssid = colander.SchemaNode(colander.String(), missing=None)


class LocateV1Schema(BaseLocateSchema):

    carrier = colander.SchemaNode(colander.String(), missing=None)
    considerIp = colander.SchemaNode(colander.Boolean(), missing=True)
    homeMobileCountryCode = colander.SchemaNode(
        colander.Integer(), missing=None)
    homeMobileNetworkCode = colander.SchemaNode(
        colander.Integer(), missing=None)
    radioType = colander.SchemaNode(
        colander.String(), validator=colander.OneOf(RADIO_STRINGS),
        missing=colander.drop, to_name='radio')

    bluetoothBeacons = BluetoothBeaconsSchema(missing=(), to_name='blue')
    cellTowers = CellTowersSchema(missing=(), to_name='cell')
    wifiAccessPoints = WifiAccessPointsSchema(missing=(), to_name='wifi')
    fallbacks = FallbackSchema(missing=None)

    def __init__(self, *args, **kw):
        super(LocateV1Schema, self).__init__(*args, **kw)
        self.fallback_defaults = self.get('fallbacks').deserialize({})

    def deserialize(self, data):
        data = super(LocateV1Schema, self).deserialize(data)
        if data['fallbacks'] is None:
            data['fallbacks'] = dict(self.fallback_defaults)
            data['fallbacks']['ipf'] = data['considerIp']
        return data

LOCATE_V1_SCHEMA = LocateV1Schema()
