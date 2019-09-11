"""
General submit specific colander schemata describing the public HTTP APIs.

This API is based on both the `Google geolocation API
<https://developers.google.com/maps/documentation/geolocation/intro>`_
and the `W3C geolocation position interface
<http://www.w3.org/TR/geolocation-API/#position_interface>`_.
"""

import colander

from ichnaea.api.schema import (
    OptionalBoundedFloatNode,
    OptionalMappingSchema,
    OptionalNode,
    OptionalIntNode,
    OptionalSequenceSchema,
    OptionalStringNode,
    OptionalStringVocabularyNode,
    UnixTimeFromInteger,
)

RADIO_STRINGS = ["gsm", "cdma", "umts", "wcdma", "lte"]
SOURCE_STRINGS = ["fixed", "gnss", "fused", "query"]


class BluetoothBeaconSchema(OptionalMappingSchema):

    macAddress = OptionalStringNode()

    age = OptionalIntNode()
    name = OptionalStringNode()
    signalStrength = OptionalIntNode()

    def deserialize(self, data):
        data = super(BluetoothBeaconSchema, self).deserialize(data)
        if "macAddress" not in data:
            return colander.drop
        return data


class BluetoothBeaconsSchema(OptionalSequenceSchema):

    blue = BluetoothBeaconSchema()


class CellTowerSchema(OptionalMappingSchema):

    radioType = OptionalStringVocabularyNode(vocabulary=RADIO_STRINGS)
    mobileCountryCode = OptionalIntNode()
    mobileNetworkCode = OptionalIntNode()
    locationAreaCode = OptionalIntNode()
    cellId = OptionalIntNode()

    age = OptionalIntNode()
    asu = OptionalIntNode()
    serving = OptionalIntNode()
    signalStrength = OptionalIntNode()
    timingAdvance = OptionalIntNode()


class WifiAccessPointSchema(OptionalMappingSchema):

    macAddress = OptionalStringNode()

    age = OptionalIntNode()
    channel = OptionalIntNode()
    frequency = OptionalIntNode()
    radioType = OptionalStringNode()
    signalStrength = OptionalIntNode()
    signalToNoiseRatio = OptionalIntNode()
    ssid = OptionalStringNode()

    def deserialize(self, data):
        data = super(WifiAccessPointSchema, self).deserialize(data)
        if "macAddress" not in data:
            return colander.drop
        return data


class WifiAccessPointsSchema(OptionalSequenceSchema):

    wifi = WifiAccessPointSchema()


class PositionSchema(OptionalMappingSchema):

    latitude = OptionalBoundedFloatNode()
    longitude = OptionalBoundedFloatNode()

    accuracy = OptionalBoundedFloatNode()
    age = OptionalIntNode()
    altitude = OptionalBoundedFloatNode()
    altitudeAccuracy = OptionalBoundedFloatNode()
    heading = OptionalBoundedFloatNode()
    pressure = OptionalBoundedFloatNode()
    speed = OptionalBoundedFloatNode()
    source = OptionalStringVocabularyNode(vocabulary=SOURCE_STRINGS)


class ReportSchema(OptionalMappingSchema):

    carrier = OptionalStringNode()
    homeMobileCountryCode = OptionalIntNode()
    homeMobileNetworkCode = OptionalIntNode()
    radioType = OptionalStringVocabularyNode(vocabulary=RADIO_STRINGS)
    timestamp = OptionalNode(UnixTimeFromInteger())

    bluetoothBeacons = BluetoothBeaconsSchema(missing=())
    wifiAccessPoints = WifiAccessPointsSchema(missing=())

    def deserialize(self, data):
        data = super(ReportSchema, self).deserialize(data)
        if data is colander.drop or data is colander.null:
            return colander.drop

        if not (
            data.get("bluetoothBeacons")
            or data.get("cellTowers")
            or data.get("wifiAccessPoints")
        ):
            return colander.drop

        top_radio = data.get("radioType", None)
        for cell in data.get("cellTowers", ()):
            if top_radio and ("radioType" not in cell or not cell["radioType"]):
                cell["radioType"] = top_radio
            if cell.get("radioType") == "umts":
                cell["radioType"] = "wcdma"

        if "radioType" in data:
            del data["radioType"]

        return data
