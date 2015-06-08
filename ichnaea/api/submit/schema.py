# This API is based on both the Google geolocation API
# https://developers.google.com/maps/documentation/business/geolocation/
# and the W3C geolocation position interface
# http://www.w3.org/TR/geolocation-API/#position_interface

from ichnaea.api.schema import (
    OptionalBoundedFloatNode,
    OptionalMappingSchema,
    OptionalNode,
    OptionalIntNode,
    OptionalSequenceSchema,
    OptionalStringNode,
    UnixTimeFromInteger,
)


class BluetoothBeaconSchema(OptionalMappingSchema):

    macAddress = OptionalStringNode()

    age = OptionalIntNode()
    name = OptionalStringNode()
    signalStrength = OptionalIntNode()


class BluetoothBeaconsSchema(OptionalSequenceSchema):

    blue = BluetoothBeaconSchema()


class CellTowerSchema(OptionalMappingSchema):

    radioType = OptionalStringNode()
    mobileCountryCode = OptionalIntNode()
    mobileNetworkCode = OptionalIntNode()
    locationAreaCode = OptionalIntNode()
    cellId = OptionalIntNode()

    age = OptionalIntNode()
    asu = OptionalIntNode()
    serving = OptionalIntNode()
    signalStrength = OptionalIntNode()
    timingAdvance = OptionalIntNode()


class ConnectionSchema(OptionalMappingSchema):

    ip = OptionalStringNode()


class WifiAccessPointSchema(OptionalMappingSchema):

    macAddress = OptionalStringNode()

    age = OptionalIntNode()
    channel = OptionalIntNode()
    frequency = OptionalIntNode()
    radioType = OptionalStringNode()
    signalStrength = OptionalIntNode()
    signalToNoiseRatio = OptionalIntNode()
    ssid = OptionalStringNode()


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
    source = OptionalStringNode()


class ReportSchema(OptionalMappingSchema):

    carrier = OptionalStringNode()
    homeMobileCountryCode = OptionalIntNode()
    homeMobileNetworkCode = OptionalIntNode()
    radioType = OptionalStringNode()
    timestamp = OptionalNode(UnixTimeFromInteger())

    wifiAccessPoints = WifiAccessPointsSchema(missing=())
