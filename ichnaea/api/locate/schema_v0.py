"""
Colander schemata describing the public v1/search HTTP API.
"""

import colander

from ichnaea.api.schema import RenamingMappingSchema
from ichnaea.api.locate.schema import BaseLocateSchema, FallbackSchema


RADIO_STRINGS = ["gsm", "cdma", "umts", "wcdma", "lte"]


class BluesSchema(colander.SequenceSchema):
    @colander.instantiate()
    class SequenceItem(RenamingMappingSchema):

        key = colander.SchemaNode(colander.String(), missing=None, to_name="macAddress")
        age = colander.SchemaNode(colander.Integer(), missing=None)
        signal = colander.SchemaNode(
            colander.Integer(), missing=None, to_name="signalStrength"
        )
        name = colander.SchemaNode(colander.String(), missing=None)


class CellsSchema(colander.SequenceSchema):
    @colander.instantiate()
    class SequenceItem(RenamingMappingSchema):

        radio = colander.SchemaNode(
            colander.String(),
            validator=colander.OneOf(RADIO_STRINGS),
            missing=None,
            to_name="radioType",
        )
        mcc = colander.SchemaNode(
            colander.Integer(), missing=None, to_name="mobileCountryCode"
        )
        mnc = colander.SchemaNode(
            colander.Integer(), missing=None, to_name="mobileNetworkCode"
        )
        lac = colander.SchemaNode(
            colander.Integer(), missing=None, to_name="locationAreaCode"
        )
        cid = colander.SchemaNode(colander.Integer(), missing=None, to_name="cellId")

        age = colander.SchemaNode(colander.Integer(), missing=None)
        asu = colander.SchemaNode(colander.Integer(), missing=None)
        psc = colander.SchemaNode(
            colander.Integer(), missing=None, to_name="primaryScramblingCode"
        )
        signal = colander.SchemaNode(
            colander.Integer(), missing=None, to_name="signalStrength"
        )
        ta = colander.SchemaNode(
            colander.Integer(), missing=None, to_name="timingAdvance"
        )


class WifisSchema(colander.SequenceSchema):
    @colander.instantiate()
    class SequenceItem(RenamingMappingSchema):

        key = colander.SchemaNode(colander.String(), missing=None, to_name="macAddress")
        age = colander.SchemaNode(colander.Integer(), missing=None)
        frequency = colander.SchemaNode(colander.Integer(), missing=None)
        channel = colander.SchemaNode(colander.Integer(), missing=None)
        signal = colander.SchemaNode(
            colander.Integer(), missing=None, to_name="signalStrength"
        )
        signalToNoiseRatio = colander.SchemaNode(colander.Integer(), missing=None)
        ssid = colander.SchemaNode(colander.String(), missing=None)


class LocateV0Schema(BaseLocateSchema):

    radio = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(RADIO_STRINGS),
        missing=None,
        to_name="radioType",
    )
    blue = BluesSchema(missing=(), to_name="bluetoothBeacons")
    cell = CellsSchema(missing=(), to_name="cellTowers")
    wifi = WifisSchema(missing=(), to_name="wifiAccessPoints")
    fallbacks = FallbackSchema(missing=None)


LOCATE_V0_SCHEMA = LocateV0Schema()
