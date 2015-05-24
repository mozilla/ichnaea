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

    # radio is a FxOS specific undocumented workaround
    radio = SchemaNode(String(),
                       validator=OneOf(RADIO_STRINGS), missing=None)
    radioType = SchemaNode(String(),
                           validator=OneOf(RADIO_STRINGS), missing=None)
    mobileCountryCode = SchemaNode(Integer(), missing=None)
    mobileNetworkCode = SchemaNode(Integer(), missing=None)
    locationAreaCode = SchemaNode(Integer(), missing=None)
    cellId = SchemaNode(Integer(), missing=None)

    age = SchemaNode(Integer(), missing=None)
    psc = SchemaNode(Integer(), missing=None)
    signalStrength = SchemaNode(Integer(), missing=None)
    timingAdvance = SchemaNode(Integer(), missing=None)


class CellTowersSchema(SequenceSchema):

    cell = CellTowerSchema()


class WifiAccessPointSchema(MappingSchema):

    macAddress = SchemaNode(String(), missing=None)

    age = SchemaNode(Integer(), missing=None)
    channel = SchemaNode(Integer(), missing=None)
    signalStrength = SchemaNode(Integer(), missing=None)
    signalToNoiseRatio = SchemaNode(Integer(), missing=None)


class WifiAccessPointsSchema(SequenceSchema):

    wifi = WifiAccessPointSchema()


class GeoLocateSchema(MappingSchema):

    carrier = SchemaNode(String(), missing=None)
    homeMobileCountryCode = SchemaNode(Integer(), missing=None)
    homeMobileNetworkCode = SchemaNode(Integer(), missing=None)
    radioType = SchemaNode(String(),
                           validator=OneOf(RADIO_STRINGS), missing=None)

    cellTowers = CellTowersSchema(missing=())
    wifiAccessPoints = WifiAccessPointsSchema(missing=())
