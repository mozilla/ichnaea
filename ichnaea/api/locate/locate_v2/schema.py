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

from ichnaea.api.schema import (
    FallbackSchema,
    InternalMapping,
    InternalMixin,
    InternalSchemaNode,
)
from ichnaea.api.locate.schema import BaseLocateSchema

RADIO_STRINGS = ['gsm', 'cdma', 'wcdma', 'lte']


class CellTowerSchema(MappingSchema):
    schema_type = InternalMapping

    # radio is a FxOS specific undocumented workaround
    radio = SchemaNode(String(), validator=OneOf(RADIO_STRINGS), missing=None)
    # radioType resolves to the internal field 'radio', so if both 'radio' and
    # 'radioType' are provided, radioType should take precedence.  colander
    # respects the order that fields are defined and so radioType is defined
    # after the 'radio' field.
    radioType = InternalSchemaNode(
        String(), validator=OneOf(RADIO_STRINGS),
        missing=None, internal_name='radio')
    mobileCountryCode = InternalSchemaNode(
        Integer(), missing=None, internal_name='mcc')
    mobileNetworkCode = InternalSchemaNode(
        Integer(), missing=None, internal_name='mnc')
    locationAreaCode = InternalSchemaNode(
        Integer(), missing=None, internal_name='lac')
    cellId = InternalSchemaNode(
        Integer(), missing=None, internal_name='cid')

    age = SchemaNode(Integer(), missing=None)
    psc = SchemaNode(Integer(), missing=None)
    signalStrength = InternalSchemaNode(
        Integer(), missing=None, internal_name='signal')
    timingAdvance = InternalSchemaNode(
        Integer(), missing=None, internal_name='ta')


class CellTowersSchema(InternalMixin, SequenceSchema):

    cell = CellTowerSchema()


class WifiAccessPointSchema(InternalMixin, MappingSchema):
    schema_type = InternalMapping

    macAddress = InternalSchemaNode(
        String(), missing=None, internal_name='key')
    age = SchemaNode(Integer(), missing=None)
    channel = SchemaNode(Integer(), missing=None)
    frequency = SchemaNode(Integer(), missing=None)
    signalStrength = InternalSchemaNode(
        Integer(), missing=None, internal_name='signal')
    signalToNoiseRatio = InternalSchemaNode(
        Integer(), missing=None, internal_name='snr')


class WifiAccessPointsSchema(InternalMixin, SequenceSchema):

    wifi = WifiAccessPointSchema()


class LocateV2Schema(BaseLocateSchema):

    carrier = InternalSchemaNode(String(), missing=None)
    homeMobileCountryCode = InternalSchemaNode(Integer(), missing=None)
    homeMobileNetworkCode = InternalSchemaNode(Integer(), missing=None)
    radioType = InternalSchemaNode(
        String(), validator=OneOf(RADIO_STRINGS),
        missing=None, internal_name='radio')

    cellTowers = CellTowersSchema(missing=(), internal_name='cell')
    wifiAccessPoints = WifiAccessPointsSchema(missing=(), internal_name='wifi')
    fallbacks = FallbackSchema(missing=None)
