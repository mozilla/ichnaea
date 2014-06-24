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

RADIO_TYPE_KEYS = ['gsm', 'cdma', 'wcdma']


class CellTowerSchema(MappingSchema):
    # required
    cellId = SchemaNode(Integer())
    locationAreaCode = SchemaNode(Integer())
    radio = SchemaNode(String(),
                       validator=OneOf(RADIO_TYPE_KEYS), missing='')
    mobileCountryCode = SchemaNode(Integer())
    mobileNetworkCode = SchemaNode(Integer())
    # optional
    age = SchemaNode(Integer(), missing=0)
    signalStrength = SchemaNode(Integer(), missing=0)
    timingAdvance = SchemaNode(Integer(), missing=0)


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
    homeMobileCountryCode = SchemaNode(Integer(), missing=-1)
    homeMobileNetworkCode = SchemaNode(Integer(), missing=-1)
    radioType = SchemaNode(String(),
                           validator=OneOf(RADIO_TYPE_KEYS), missing='')
    carrier = SchemaNode(String(), missing='')
    cellTowers = CellTowersSchema(missing=())
    wifiAccessPoints = WifiAccessPointsSchema(missing=())
