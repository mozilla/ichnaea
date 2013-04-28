from colander import MappingSchema, SchemaNode, SequenceSchema
from colander import Decimal, Integer, String, OneOf, Range


class CellSchema(MappingSchema):
    mcc = SchemaNode(Integer(),
                     location="body", type='int', validator=Range(0, 1000))
    mnc = SchemaNode(Integer(),
                     location="body", type='int', validator=Range(0, 32767))
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
    lat = SchemaNode(Decimal(quant="1.000000"), location="body")
    lon = SchemaNode(Decimal(quant="1.000000"), location="body")
    accuracy = SchemaNode(Integer(), location="body", type='int',
                          missing=0, validator=Range(0, 32767))
    altitude = SchemaNode(Integer(), location="body", type='int',
                          missing=0, validator=Range(-32768, 32767))
    altitude_accuracy = SchemaNode(Integer(), location="body", type='int',
                                   missing=0, validator=Range(0, 32767))
    radio = SchemaNode(String(), location="body", type='str',
                       validator=OneOf(['gsm', 'cdma']), missing='gsm')
    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())
