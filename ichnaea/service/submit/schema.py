from colander import (
    Integer,
    MappingSchema,
    SchemaNode,
    SequenceSchema,
    String,
)

from ichnaea.service.schema import BoundedFloat


class CellSchema(MappingSchema):

    radio = SchemaNode(String(), missing=None)
    mcc = SchemaNode(Integer(), missing=None)
    mnc = SchemaNode(Integer(), missing=None)
    lac = SchemaNode(Integer(), missing=None)
    cid = SchemaNode(Integer(), missing=None)

    age = SchemaNode(Integer(), missing=None)
    asu = SchemaNode(Integer(), missing=None)
    psc = SchemaNode(Integer(), missing=None)
    serving = SchemaNode(Integer(), missing=None)
    signal = SchemaNode(Integer(), missing=None)
    ta = SchemaNode(Integer(), missing=None)


class CellsSchema(SequenceSchema):

    cell = CellSchema()


class WifiSchema(MappingSchema):

    key = SchemaNode(String())

    age = SchemaNode(Integer(), missing=None)
    channel = SchemaNode(Integer(), missing=None)
    frequency = SchemaNode(Integer(), missing=None)
    radio = SchemaNode(String(), missing=None)
    signal = SchemaNode(Integer(), missing=None)
    signalToNoiseRatio = SchemaNode(Integer(), missing=None)


class WifisSchema(SequenceSchema):

    wifi = WifiSchema()


class BaseReportSchema(MappingSchema):

    lat = SchemaNode(BoundedFloat(), missing=None)
    lon = SchemaNode(BoundedFloat(), missing=None)

    time = SchemaNode(String(), missing=None)
    accuracy = SchemaNode(Integer(), missing=None)
    age = SchemaNode(Integer(), missing=None)
    altitude = SchemaNode(Integer(), missing=None)
    altitude_accuracy = SchemaNode(Integer(), missing=None)
    heading = SchemaNode(BoundedFloat(), missing=None)
    pressure = SchemaNode(BoundedFloat(), missing=None)
    radio = SchemaNode(String(), missing=None)
    speed = SchemaNode(BoundedFloat(), missing=None)
    source = SchemaNode(String(), missing=None)


class ReportSchema(BaseReportSchema):

    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())


class ReportsSchema(SequenceSchema):

    report = ReportSchema()


class SubmitSchema(MappingSchema):

    items = ReportsSchema()
