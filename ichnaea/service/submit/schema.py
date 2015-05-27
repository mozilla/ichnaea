from ichnaea.service.schema import (
    OptionalBoundedFloatNode,
    OptionalIntNode,
    OptionalMappingSchema,
    OptionalNode,
    OptionalSequenceSchema,
    OptionalStringNode,
    UnixTimeFromString,
)


class CellSchema(OptionalMappingSchema):

    radio = OptionalStringNode()
    mcc = OptionalIntNode()
    mnc = OptionalIntNode()
    lac = OptionalIntNode()
    cid = OptionalIntNode()

    age = OptionalIntNode()
    asu = OptionalIntNode()
    psc = OptionalIntNode()
    serving = OptionalIntNode()
    signal = OptionalIntNode()
    ta = OptionalIntNode()


class CellsSchema(OptionalSequenceSchema):

    cell = CellSchema()


class WifiSchema(OptionalMappingSchema):

    key = OptionalStringNode()

    age = OptionalIntNode()
    channel = OptionalIntNode()
    frequency = OptionalIntNode()
    radio = OptionalStringNode()
    signal = OptionalIntNode()
    signalToNoiseRatio = OptionalIntNode()


class WifisSchema(OptionalSequenceSchema):

    wifi = WifiSchema()


class BaseReportSchema(OptionalMappingSchema):

    lat = OptionalBoundedFloatNode()
    lon = OptionalBoundedFloatNode()

    time = OptionalNode(UnixTimeFromString())
    accuracy = OptionalIntNode()
    age = OptionalIntNode()
    altitude = OptionalIntNode()
    altitude_accuracy = OptionalIntNode()
    heading = OptionalBoundedFloatNode()
    pressure = OptionalBoundedFloatNode()
    radio = OptionalStringNode()
    speed = OptionalBoundedFloatNode()
    source = OptionalStringNode()


class ReportSchema(BaseReportSchema):

    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())


class ReportsSchema(OptionalSequenceSchema):

    report = ReportSchema()


class SubmitSchema(OptionalMappingSchema):

    items = ReportsSchema()
