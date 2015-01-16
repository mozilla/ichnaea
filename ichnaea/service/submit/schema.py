from colander import MappingSchema, SchemaNode, SequenceSchema
from colander import Float, Integer, String, OneOf

from ichnaea.models import RADIO_TYPE_KEYS


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


class BaseMeasureSchema(MappingSchema):
    # lat/lon being set to -255 indicates that this measure should be
    # skipped.  Other fields can be filled in with defaults
    lat = SchemaNode(Float(), missing=-255)
    lon = SchemaNode(Float(), missing=-255)

    time = SchemaNode(String(), missing='')
    accuracy = SchemaNode(Integer(), missing=0)
    altitude = SchemaNode(Integer(), missing=0)
    altitude_accuracy = SchemaNode(Integer(), missing=0)
    radio = SchemaNode(String(),
                       validator=OneOf(RADIO_TYPE_KEYS), missing='')

    heading = SchemaNode(Float(), missing=-1.0)
    speed = SchemaNode(Float(), missing=-1.0)


class MeasureSchema(BaseMeasureSchema):
    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())


class MeasuresSchema(SequenceSchema):
    measure = MeasureSchema()


class SubmitSchema(MappingSchema):
    items = MeasuresSchema()
