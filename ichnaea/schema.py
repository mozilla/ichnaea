from colander import MappingSchema, SchemaNode, SequenceSchema
from colander import Decimal, Integer, String, OneOf

from ichnaea.decimaljson import EXPONENT_STR
from ichnaea.db import RADIO_TYPE_KEYS


class CellSchema(MappingSchema):
    mcc = SchemaNode(Integer(), location="body", type='int', missing=0)
    mnc = SchemaNode(Integer(), location="body", type='int', missing=0)
    lac = SchemaNode(Integer(), location="body", type='int', missing=0)
    cid = SchemaNode(Integer(), location="body", type='int', missing=0)
    psc = SchemaNode(Integer(), location="body", type='int', missing=0)
    asu = SchemaNode(Integer(), location="body", type='int', missing=0)
    signal = SchemaNode(Integer(), location="body", type='int', missing=0)
    ta = SchemaNode(Integer(), location="body", type='int', missing=0)


class CellsSchema(SequenceSchema):
    cell = CellSchema()


class WifiSchema(MappingSchema):
    key = SchemaNode(String(), location="body", type='str')
    frequency = SchemaNode(Integer(), location="body", type='int', missing=0)
    channel = SchemaNode(Integer(), location="body", type='int', missing=0)
    signal = SchemaNode(Integer(), location="body", type='int', missing=0)


class WifisSchema(SequenceSchema):
    wifi = WifiSchema()


class SearchSchema(MappingSchema):
    radio = SchemaNode(String(), location="body", type='str',
                       validator=OneOf(RADIO_TYPE_KEYS), missing='')
    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())


class MeasureSchema(MappingSchema):
    lat = SchemaNode(Decimal(quant=EXPONENT_STR), location="body")
    lon = SchemaNode(Decimal(quant=EXPONENT_STR), location="body")
    time = SchemaNode(String(), location="body", missing='')
    # TODO remove `token` after August 12th, 2013
    token = SchemaNode(String(), location="body", missing='')
    accuracy = SchemaNode(Integer(), location="body", type='int', missing=0)
    altitude = SchemaNode(Integer(), location="body", type='int', missing=0)
    altitude_accuracy = SchemaNode(Integer(), location="body", type='int',
                                   missing=0)
    radio = SchemaNode(String(), location="body", type='str',
                       validator=OneOf(RADIO_TYPE_KEYS), missing='')
    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())


class MeasuresSchema(SequenceSchema):
    measure = MeasureSchema()


class SubmitSchema(MappingSchema):
    items = MeasuresSchema()
