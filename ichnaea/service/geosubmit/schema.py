# This API is based on both the Google geolocation API
# https://developers.google.com/maps/documentation/business/geolocation/
# and the W3C geolocation position interface
# http://www.w3.org/TR/geolocation-API/#position_interface

from colander import (
    Integer,
    MappingSchema,
    SchemaNode,
    SequenceSchema,
    String,
)

from ichnaea.service.schema import BoundedFloat


class CellTowerSchema(MappingSchema):

    radioType = SchemaNode(String(), missing=None)
    mobileCountryCode = SchemaNode(Integer(), missing=None)
    mobileNetworkCode = SchemaNode(Integer(), missing=None)
    locationAreaCode = SchemaNode(Integer(), missing=None)
    cellId = SchemaNode(Integer(), missing=None)

    age = SchemaNode(Integer(), missing=None)
    asu = SchemaNode(Integer(), missing=None)
    psc = SchemaNode(Integer(), missing=None)
    serving = SchemaNode(Integer(), missing=None)
    signalStrength = SchemaNode(Integer(), missing=None)
    timingAdvance = SchemaNode(Integer(), missing=None)


class CellTowersSchema(SequenceSchema):

    cell = CellTowerSchema()


class WifiAccessPointSchema(MappingSchema):

    macAddress = SchemaNode(String(), missing=None)

    age = SchemaNode(Integer(), missing=None)
    channel = SchemaNode(Integer(), missing=None)
    frequency = SchemaNode(Integer(), missing=None)
    radioType = SchemaNode(String(), missing=None)
    signalStrength = SchemaNode(Integer(), missing=None)
    signalToNoiseRatio = SchemaNode(Integer(), missing=None)
    ssid = SchemaNode(String(), missing=None)


class WifiAccessPointsSchema(SequenceSchema):

    wifi = WifiAccessPointSchema()


class ReportSchema(MappingSchema):

    carrier = SchemaNode(String(), missing=None)
    homeMobileCountryCode = SchemaNode(Integer(), missing=None)
    homeMobileNetworkCode = SchemaNode(Integer(), missing=None)
    radioType = SchemaNode(String(), missing=None)
    timestamp = SchemaNode(Integer(), missing=None)

    cellTowers = CellTowersSchema(missing=())
    wifiAccessPoints = WifiAccessPointsSchema(missing=())

    latitude = SchemaNode(BoundedFloat(), missing=None)
    longitude = SchemaNode(BoundedFloat(), missing=None)

    accuracy = SchemaNode(BoundedFloat(), missing=None)
    age = SchemaNode(Integer(), missing=None)
    altitude = SchemaNode(BoundedFloat(), missing=None)
    altitudeAccuracy = SchemaNode(BoundedFloat(), missing=None)
    heading = SchemaNode(BoundedFloat(), missing=None)
    pressure = SchemaNode(Integer(), missing=None)
    speed = SchemaNode(BoundedFloat(), missing=None)
    source = SchemaNode(String(), missing=None)


class ReportsSchema(SequenceSchema):
    report = ReportSchema()


class GeoSubmitSchema(MappingSchema):
    items = ReportsSchema()
