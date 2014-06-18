from colander import MappingSchema, SchemaNode, SequenceSchema
from colander import Integer, String, OneOf

from ichnaea.models import RADIO_TYPE_KEYS


class CellSchema(MappingSchema):
    radio = SchemaNode(String(), type='str',
                       validator=OneOf(RADIO_TYPE_KEYS), missing='')
    mcc = SchemaNode(Integer(), type='int', missing=-1)
    mnc = SchemaNode(Integer(), type='int', missing=-1)
    lac = SchemaNode(Integer(), type='int', missing=-1)
    cid = SchemaNode(Integer(), type='int', missing=-1)
    psc = SchemaNode(Integer(), type='int', missing=-1)
    asu = SchemaNode(Integer(), type='int', missing=-1)
    signal = SchemaNode(Integer(), type='int', missing=0)
    ta = SchemaNode(Integer(), type='int', missing=0)


class CellsSchema(SequenceSchema):
    cell = CellSchema()


class WifiSchema(MappingSchema):
    key = SchemaNode(String(), type='str')
    frequency = SchemaNode(Integer(), type='int', missing=0)
    channel = SchemaNode(Integer(), type='int', missing=0)
    signal = SchemaNode(Integer(), type='int', missing=0)
    signalToNoiseRatio = SchemaNode(
        Integer(), location="body", type='int', missing=0)


class WifisSchema(SequenceSchema):
    wifi = WifiSchema()


class SearchSchema(MappingSchema):
    radio = SchemaNode(String(), type='str',
                       validator=OneOf(RADIO_TYPE_KEYS), missing='')
    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())
