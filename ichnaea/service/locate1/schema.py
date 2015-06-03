from colander import MappingSchema, SchemaNode, SequenceSchema
from colander import Integer, String, OneOf

from ichnaea.service.schema import FallbackSchema


RADIO_STRINGS = ['gsm', 'cdma', 'umts', 'wcdma', 'lte']


class CellSchema(MappingSchema):

    radio = SchemaNode(String(),
                       validator=OneOf(RADIO_STRINGS), missing=None)
    mcc = SchemaNode(Integer(), missing=None)
    mnc = SchemaNode(Integer(), missing=None)
    lac = SchemaNode(Integer(), missing=None)
    cid = SchemaNode(Integer(), missing=None)

    asu = SchemaNode(Integer(), missing=None)
    psc = SchemaNode(Integer(), missing=None)
    signal = SchemaNode(Integer(), missing=None)
    ta = SchemaNode(Integer(), missing=None)


class CellsSchema(SequenceSchema):

    cell = CellSchema()


class WifiSchema(MappingSchema):

    key = SchemaNode(String(), missing=None)
    frequency = SchemaNode(Integer(), missing=None)
    channel = SchemaNode(Integer(), missing=None)
    signal = SchemaNode(Integer(), missing=None)
    signalToNoiseRatio = SchemaNode(Integer(), missing=None)


class WifisSchema(SequenceSchema):

    wifi = WifiSchema()


class Locate1Schema(MappingSchema):

    radio = SchemaNode(String(),
                       validator=OneOf(RADIO_STRINGS), missing=None)
    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())
    fallbacks = FallbackSchema(missing=None)
