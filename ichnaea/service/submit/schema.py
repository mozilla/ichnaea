from colander import MappingSchema, SchemaNode, SequenceSchema
from colander import Decimal, Integer, String, OneOf, Float

from ichnaea.decimaljson import EXPONENT_STR
from ichnaea.models import RADIO_TYPE_KEYS


class CellSchema(MappingSchema):
    radio = SchemaNode(String(), location="body", type='str',
                       validator=OneOf(RADIO_TYPE_KEYS), missing='')
    mcc = SchemaNode(Integer(), location="body", type='int', missing=-1)
    mnc = SchemaNode(Integer(), location="body", type='int', missing=-1)
    lac = SchemaNode(Integer(), location="body", type='int', missing=-1)
    cid = SchemaNode(Integer(), location="body", type='int', missing=-1)
    psc = SchemaNode(Integer(), location="body", type='int', missing=-1)
    asu = SchemaNode(Integer(), location="body", type='int', missing=-1)
    signal = SchemaNode(Integer(), location="body", type='int', missing=0)
    ta = SchemaNode(Integer(), location="body", type='int', missing=0)


class CellsSchema(SequenceSchema):
    cell = CellSchema()


class WifiSchema(MappingSchema):
    key = SchemaNode(String(), location="body", type='str')
    frequency = SchemaNode(Integer(), location="body", type='int', missing=0)
    channel = SchemaNode(Integer(), location="body", type='int', missing=0)
    signal = SchemaNode(Integer(), location="body", type='int', missing=0)
    signalToNoiseRatio = SchemaNode(
        Integer(), location="body", type='int', missing=0)


class WifisSchema(SequenceSchema):
    wifi = WifiSchema()


class MeasureSchema(MappingSchema):
    # lat/lon being set to -255 indicates that this measure should be
    # skipped.  Other fields can be filled in with defaults
    lat = SchemaNode(Decimal(quant=EXPONENT_STR), location="body",
                     missing=-255)
    lon = SchemaNode(Decimal(quant=EXPONENT_STR), location="body",
                     missing=-255)

    time = SchemaNode(String(), location="body", missing='')
    accuracy = SchemaNode(Integer(), location="body", type='int', missing=0)
    altitude = SchemaNode(Integer(), location="body", type='int', missing=0)
    altitude_accuracy = SchemaNode(Integer(), location="body", type='int',
                                   missing=0)
    radio = SchemaNode(String(), location="body", type='str',
                       validator=OneOf(RADIO_TYPE_KEYS), missing='')

    heading = SchemaNode(Float(), location="body", missing=-1)
    speed = SchemaNode(Float(), location="body", missing=-1)

    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())


class MeasuresSchema(SequenceSchema):
    measure = MeasureSchema()


class SubmitSchema(MappingSchema):
    items = MeasuresSchema()
