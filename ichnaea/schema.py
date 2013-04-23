from colander import MappingSchema, SchemaNode, SequenceSchema
from colander import Decimal, Integer, String, OneOf


class CellSchema(MappingSchema):
    mcc = SchemaNode(Integer(), location="body", type='int')
    mnc = SchemaNode(Integer(), location="body", type='int')
    lac = SchemaNode(Integer(), location="body", type='int')
    cid = SchemaNode(Integer(), location="body", type='int')
    signal = SchemaNode(Integer(), location="body", type='int', missing=0)


class CellsSchema(SequenceSchema):
    cell = CellSchema()


class WifiSchema(MappingSchema):
    mac = SchemaNode(String(), location="body", type='str')
    channel = SchemaNode(Integer(), location="body", type='int', missing=0)
    noise = SchemaNode(Integer(), location="body", type='int', missing=0)
    signal = SchemaNode(Integer(), location="body", type='int', missing=0)


class WifisSchema(SequenceSchema):
    wifi = WifiSchema()


class SearchSchema(MappingSchema):
    radio = SchemaNode(String(), location="body", type='str',
                       validator=OneOf(['gsm', 'cdma']), missing='gsm')
    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())


class MeasureSchema(MappingSchema):
    lat = SchemaNode(Decimal(quant="1.000000"), location="path")
    lon = SchemaNode(Decimal(quant="1.000000"), location="path")
    radio = SchemaNode(String(), location="body", type='str',
                       validator=OneOf(['gsm', 'cdma']), missing='gsm')
    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())
