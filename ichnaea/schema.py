from colander import MappingSchema, SchemaNode, SequenceSchema
from colander import DateTime, Decimal, Integer, String, OneOf, Range

from ichnaea.decimaljson import EXPONENT_STR
from ichnaea.db import RADIO_TYPE_KEYS


class CellSchema(MappingSchema):
    mcc = SchemaNode(Integer(), location="body", type='int',
                     validator=Range(0, 1000))
    mnc = SchemaNode(Integer(), location="body", type='int',
                     validator=Range(0, 32767))
    lac = SchemaNode(Integer(), location="body", type='int',
                     validator=Range(0, 2147483647), missing=0)
    cid = SchemaNode(Integer(), location="body", type='int',
                     validator=Range(0, 268435455), missing=0)
    psc = SchemaNode(Integer(), location="body", type='int',
                     validator=Range(0, 511), missing=0)
    asu = SchemaNode(Integer(), location="body", type='int',
                     validator=Range(-5, 255), missing=0)
    signal = SchemaNode(Integer(), location="body", type='int', missing=0)
    ta = SchemaNode(Integer(), location="body", type='int',
                    validator=Range(0, 63), missing=0)


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
    time = SchemaNode(DateTime(), location="body", missing=None)
    accuracy = SchemaNode(Integer(), location="body", type='int',
                          missing=0, validator=Range(0, 32767))
    altitude = SchemaNode(Integer(), location="body", type='int',
                          missing=0, validator=Range(-32768, 32767))
    altitude_accuracy = SchemaNode(Integer(), location="body", type='int',
                                   missing=0, validator=Range(0, 32767))
    radio = SchemaNode(String(), location="body", type='str',
                       validator=OneOf(RADIO_TYPE_KEYS), missing='')
    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())


class MeasuresSchema(SequenceSchema):
    measure = MeasureSchema()


class SubmitSchema(MappingSchema):
    items = MeasuresSchema()
