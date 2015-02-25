# matches the schema definition of:
# https://developers.google.com/maps/documentation/business/geolocation/

from colander import (
    Integer,
    MappingSchema,
    OneOf,
    SchemaNode,
    SequenceSchema,
    String,
)

RADIO_STRINGS = ['gsm', 'cdma', 'wcdma', 'lte']


class CellTowerSchema(MappingSchema):
    # required
    cellId = SchemaNode(Integer(), missing=None)
    locationAreaCode = SchemaNode(Integer(), missing=None)
    radio = SchemaNode(String(),
                       validator=OneOf(RADIO_STRINGS), missing=None)
    mobileCountryCode = SchemaNode(Integer())
    mobileNetworkCode = SchemaNode(Integer())
    # optional
    age = SchemaNode(Integer(), missing=0)
    signalStrength = SchemaNode(Integer(), missing=0)
    timingAdvance = SchemaNode(Integer(), missing=0)

    # The fields below are extra fields which are not part of the
    # official geolocate API
    psc = SchemaNode(Integer(), missing=None)


class CellTowersSchema(SequenceSchema):
    cell = CellTowerSchema()


class WifiAccessPointSchema(MappingSchema):
    # required
    macAddress = SchemaNode(String())
    # optional
    signalStrength = SchemaNode(Integer(), missing=0)
    age = SchemaNode(Integer(), missing=0)
    channel = SchemaNode(Integer(), missing=0)
    signalToNoiseRatio = SchemaNode(Integer(), missing=0)


class WifiAccessPointsSchema(SequenceSchema):
    wifi = WifiAccessPointSchema()


class GeoLocateSchema(MappingSchema):
    homeMobileCountryCode = SchemaNode(Integer(), missing=None)
    homeMobileNetworkCode = SchemaNode(Integer(), missing=None)
    radioType = SchemaNode(String(),
                           validator=OneOf(RADIO_STRINGS), missing=None)
    carrier = SchemaNode(String(), missing='')
    cellTowers = CellTowersSchema(missing=())
    wifiAccessPoints = WifiAccessPointsSchema(missing=())
