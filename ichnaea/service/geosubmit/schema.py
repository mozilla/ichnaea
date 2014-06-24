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
    # mapped to 'cid' for submit
    cellId = SchemaNode(Integer())
    # mapped to 'lac' for submit
    locationAreaCode = SchemaNode(Integer())
    # mapped to 'mcc' for submit
    mobileCountryCode = SchemaNode(Integer())
    # mapped to 'mnc' for submit
    mobileNetworkCode = SchemaNode(Integer())

    # optional
    age = SchemaNode(Integer(), missing=0)
    # mapped to 'signal' for submit
    signalStrength = SchemaNode(Integer(), missing=0)
    # mapped to 'ta' for submit
    timingAdvance = SchemaNode(Integer(), missing=0)

    # The fields below are extra fields which are not part of the
    # geolocate API, but assist with data submission
    psc = SchemaNode(Integer(), missing=-1)
    asu = SchemaNode(Integer(), missing=-1)


class CellTowersSchema(SequenceSchema):
    cell = CellTowerSchema()


class WifiAccessPointSchema(MappingSchema):
    # mapped to 'key' for submit
    macAddress = SchemaNode(String())

    # mapped to 'signal' for submit
    signalStrength = SchemaNode(Integer(), missing=0)
    age = SchemaNode(Integer(), missing=0)
    channel = SchemaNode(Integer(), missing=0)
    signalToNoiseRatio = SchemaNode(Integer(), missing=0)

    # The fields below are extra fields which are not part of the
    # geolocate API, but assist with data submission
    frequency = SchemaNode(Integer(), missing=0)


class WifiAccessPointsSchema(SequenceSchema):
    wifi = WifiAccessPointSchema()


class GeoSubmitSchema(MappingSchema):
    # The first portion of the GeoSubmitSchema is identical to the
    # Gelocate schema with the exception that the radioType validator
    # can accept one more radioType (lte)
    homeMobileCountryCode = SchemaNode(
        Integer(), missing=-1)
    homeMobileNetworkCode = SchemaNode(
        Integer(), missing=-1)

    # mapped to 'radio' for submit
    radioType = SchemaNode(String(),
                           validator=OneOf(GEOSUBMIT_RADIO_TYPE_KEYS),
                           missing='')
    carrier = SchemaNode(String(), missing='')
    cellTowers = CellTowersSchema(missing=())
    wifiAccessPoints = WifiAccessPointsSchema(missing=())

    # The fields below are extra fields which are not part of the
    # geolocate API, but are part of the submit schema

    # mapped to 'lat' for submit
    latitude = SchemaNode(Float(), missing=-255)

    # mapped to 'lon' for submit
    longitude = SchemaNode(Float(), missing=-255)

    # parsed and mapped to 'time' for submit
    timestamp = SchemaNode(Integer(), missing=0)

    # mapped to 'accuracy' for submit
    accuracy = SchemaNode(Float(), missing=0)

    # mapped to 'altitude' for submit
    altitude = SchemaNode(Float(), missing=0)

    # mapped to 'altitude_accuracy' for submit
    altitudeAccuracy = SchemaNode(Float(), missing=0)
    # radio is taken from radioType
    # cell is taken from cellTowers
    # wifi is taken from wifiAccessPoints

    heading = SchemaNode(Float(), missing=-1.0)
    speed = SchemaNode(Float(), missing=-1.0)


class GeoSubmitListSchema(SequenceSchema):
    measure = GeoSubmitSchema()


class GeoSubmitBatchSchema(MappingSchema):
    items = GeoSubmitListSchema()
