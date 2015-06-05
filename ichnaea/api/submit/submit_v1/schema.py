from ichnaea.api.schema import (
    OptionalBoundedFloatNode,
    OptionalIntNode,
    OptionalMappingSchema,
    OptionalNode,
    OptionalSequenceSchema,
    OptionalStringNode,
    UnixTimeFromString,
)


class CellV1Schema(OptionalMappingSchema):

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


class CellsV1Schema(OptionalSequenceSchema):

    cell = CellV1Schema()


class WifiV1Schema(OptionalMappingSchema):

    key = OptionalStringNode()

    age = OptionalIntNode()
    channel = OptionalIntNode()
    frequency = OptionalIntNode()
    radio = OptionalStringNode()
    signal = OptionalIntNode()
    signalToNoiseRatio = OptionalIntNode()


class WifisV1Schema(OptionalSequenceSchema):

    wifi = WifiV1Schema()


class BaseReportV1Schema(OptionalMappingSchema):

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


class ReportV1Schema(BaseReportV1Schema):

    cell = CellsV1Schema(missing=())
    wifi = WifisV1Schema(missing=())


class ReportsV1Schema(OptionalSequenceSchema):

    report = ReportV1Schema()


class SubmitV1Schema(OptionalMappingSchema):

    items = ReportsV1Schema()
