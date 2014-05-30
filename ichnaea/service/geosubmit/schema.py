# This API is based on both the Google geolocation API
# https://developers.google.com/maps/documentation/business/geolocation/
# and the W3C geolocation position interface
# http://www.w3.org/TR/geolocation-API/#position_interface

from colander import (
    Float,
    Integer,
    MappingSchema,
    OneOf,
    SchemaNode,
    SequenceSchema,
    String,
)
from ichnaea.service.geolocate.schema import RADIO_TYPE_KEYS

GEOSUBMIT_RADIO_TYPE_KEYS = list(set(RADIO_TYPE_KEYS + ['lte']))


class CellTowerSchema(MappingSchema):
    # From geolocate
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

    # The fields below are extra fields which are not part of the
    # geolocate API, but assist with data submission
    psc = SchemaNode(Integer(), location="body",
                     type='int', missing=-1)
    asu = SchemaNode(Integer(), location="body",
                     type='int', missing=-1)


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

    # The fields below are extra fields which are not part of the
    # geolocate API, but assist with data submission
    frequency = SchemaNode(Integer(), location="body",
                           type='int', missing=0)


class WifiAccessPointsSchema(SequenceSchema):
    wifi = WifiAccessPointSchema()


class GeoSubmitSchema(MappingSchema):
    # The first portion of the GeoSubmitSchema is identical to the
    # Gelocate schema with the exception that the radioType validator
    # can accept one more radioType (lte)
    homeMobileCountryCode = SchemaNode(
        Integer(), location="body", type='int', missing=0)
    homeMobileNetworkCode = SchemaNode(
        Integer(), location="body", type='int', missing=0)
    radioType = SchemaNode(String(), location="body", type='str',
                           validator=OneOf(GEOSUBMIT_RADIO_TYPE_KEYS),
                           missing='')
    carrier = SchemaNode(String(), location="body", missing='')
    cellTowers = CellTowersSchema(missing=())
    wifiAccessPoints = WifiAccessPointsSchema(missing=())

    # The fields below are extra fields which are not part of the
    # geolocate API, but assist with data submission
    latitude = SchemaNode(Float(), location="body", missing=-255)
    longitude = SchemaNode(Float(), location="body", missing=-255)
    accuracy = SchemaNode(Float(), location="body", missing=0)
    altitude = SchemaNode(Float(), location="body", type='int', missing=0)
    altitudeAccuracy = SchemaNode(Float(), location="body", missing=0)
    heading = SchemaNode(Float(), location="body", missing=-255)
    speed = SchemaNode(Float(), location="body", missing=-255)
    timestamp = SchemaNode(Integer(), type='long', location="body", missing=0)
