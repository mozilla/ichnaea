from colander import MappingSchema, SchemaNode, SequenceSchema
from colander import Integer, String


class CellSchema(MappingSchema):
    mcc = SchemaNode(Integer(), location="body", type='int')
    mnc = SchemaNode(Integer(), location="body", type='int')
    lac = SchemaNode(Integer(), location="body", type='int')
    cid = SchemaNode(Integer(), location="body", type='int')
    strength = SchemaNode(Integer(), location="body", type='int', missing=0)


class CellsSchema(SequenceSchema):
    cell = CellSchema()


class WifiSchema(MappingSchema):
    bssid = SchemaNode(String(), location="body", type='str')
    strength = SchemaNode(Integer(), location="body", type='int', missing=0)


class WifisSchema(SequenceSchema):
    wifi = WifiSchema()


class SearchSchema(MappingSchema):
    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())


class MeasureSchema(MappingSchema):
    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())
