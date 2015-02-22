from colander import MappingSchema, SchemaNode, SequenceSchema
from colander import Integer, String, OneOf

RADIO_TYPE_KEYS = ['gsm', 'cdma', 'umts', 'wcdma', 'lte']


class CellSchema(MappingSchema):
    radio = SchemaNode(String(),
                       validator=OneOf(RADIO_TYPE_KEYS), missing='')
    mcc = SchemaNode(Integer(), missing=-1)
    mnc = SchemaNode(Integer(), missing=-1)
    lac = SchemaNode(Integer(), missing=-1)
    cid = SchemaNode(Integer(), missing=-1)
    psc = SchemaNode(Integer(), missing=-1)
    asu = SchemaNode(Integer(), missing=-1)
    signal = SchemaNode(Integer(), missing=0)
    ta = SchemaNode(Integer(), missing=0)


class CellsSchema(SequenceSchema):
    cell = CellSchema()


class WifiSchema(MappingSchema):
    key = SchemaNode(String())
    frequency = SchemaNode(Integer(), missing=0)
    channel = SchemaNode(Integer(), missing=0)
    signal = SchemaNode(Integer(), missing=0)
    signalToNoiseRatio = SchemaNode(Integer(), missing=0)


class WifisSchema(SequenceSchema):
    wifi = WifiSchema()


class SearchSchema(MappingSchema):
    radio = SchemaNode(String(),
                       validator=OneOf(RADIO_TYPE_KEYS), missing='')
    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())
