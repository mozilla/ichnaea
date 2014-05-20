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
    cellId = SchemaNode(Integer(), location="body", type='int')
    locationAreaCode = SchemaNode(Integer(), location="body", type='int')
    radio = SchemaNode(String(), location="body", type='str',
                       validator=OneOf(RADIO_TYPE_KEYS), missing='')
    mobileCountryCode = SchemaNode(Integer(), location="body", type='int')
    mobileNetworkCode = SchemaNode(Integer(), location="body", type='int')
    # optional
    age = SchemaNode(
        Integer(), location="body", type='int', missing=0)
    signalStrength = SchemaNode(
        Integer(), location="body", type='int', missing=0)
    timingAdvance = SchemaNode(
        Integer(), location="body", type='int', missing=0)


class CellTowersSchema(SequenceSchema):
    cell = CellTowerSchema()


class WifiAccessPointSchema(MappingSchema):
    # required
    macAddress = SchemaNode(String(), location="body", type='str')
    # optional
    signalStrength = SchemaNode(
        Integer(), location="body", type='int', missing=0)
    age = SchemaNode(
        Integer(), location="body", type='int', missing=0)
    channel = SchemaNode(
        Integer(), location="body", type='int', missing=0)
    signalToNoiseRatio = SchemaNode(
        Integer(), location="body", type='int', missing=0)


class WifiAccessPointsSchema(SequenceSchema):
    wifi = WifiAccessPointSchema()


class GeoLocateSchema(MappingSchema):
    homeMobileCountryCode = SchemaNode(
        Integer(), location="body", type='int', missing=0)
    homeMobileNetworkCode = SchemaNode(
        Integer(), location="body", type='int', missing=0)
    radioType = SchemaNode(String(), location="body", type='str',
                           validator=OneOf(RADIO_TYPE_KEYS), missing='')
    carrier = SchemaNode(String(), location="body", missing='')
    cellTowers = CellTowersSchema(missing=())
    wifiAccessPoints = WifiAccessPointsSchema(missing=())
