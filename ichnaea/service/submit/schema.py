from colander import MappingSchema, SchemaNode, SequenceSchema
from colander import Integer, String

from ichnaea.service.schema import BoundedFloat


class CellSchema(MappingSchema):
    radio = SchemaNode(String(), missing=None)
    mcc = SchemaNode(Integer(), missing=-1)
    mnc = SchemaNode(Integer(), missing=-1)
    lac = SchemaNode(Integer(), missing=-1)
    cid = SchemaNode(Integer(), missing=-1)
    psc = SchemaNode(Integer(), missing=-1)
    asu = SchemaNode(Integer(), missing=-1)
    signal = SchemaNode(Integer(), missing=0)
    ta = SchemaNode(Integer(), missing=0)

    age = SchemaNode(Integer(), missing=None)
    serving = SchemaNode(Integer(), missing=None)


class CellsSchema(SequenceSchema):
    cell = CellSchema()


class WifiSchema(MappingSchema):
    key = SchemaNode(String())
    frequency = SchemaNode(Integer(), missing=0)
    channel = SchemaNode(Integer(), missing=0)
    signal = SchemaNode(Integer(), missing=0)
    signalToNoiseRatio = SchemaNode(Integer(), missing=0)

    radio = SchemaNode(String(), missing=None)
    age = SchemaNode(Integer(), missing=None)


class WifisSchema(SequenceSchema):
    wifi = WifiSchema()


class BaseReportSchema(MappingSchema):
    lat = SchemaNode(BoundedFloat(), missing=None)
    lon = SchemaNode(BoundedFloat(), missing=None)

    time = SchemaNode(String(), missing='')
    accuracy = SchemaNode(Integer(), missing=0)
    altitude = SchemaNode(Integer(), missing=0)
    altitude_accuracy = SchemaNode(Integer(), missing=0)
    radio = SchemaNode(String(), missing=None)

    heading = SchemaNode(BoundedFloat(), missing=-1.0)
    speed = SchemaNode(BoundedFloat(), missing=-1.0)

    age = SchemaNode(Integer(), missing=None)
    source = SchemaNode(String(), missing='gps')
    pressure = SchemaNode(Integer(), missing=None)


class ReportSchema(BaseReportSchema):
    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())


class ReportsSchema(SequenceSchema):
    report = ReportSchema()


class SubmitSchema(MappingSchema):
    items = ReportsSchema()
