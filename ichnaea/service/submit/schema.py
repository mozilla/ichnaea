from colander import MappingSchema, SchemaNode, SequenceSchema
from colander import Float, Integer, String, OneOf

RADIO_TYPE_KEYS = ['gsm', 'cdma', 'umts', 'wcdma', 'lte']


class CellSchema(MappingSchema):
    radio = SchemaNode(String(),
                       validator=OneOf(RADIO_TYPE_KEYS), missing=None)
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


class BaseReportSchema(MappingSchema):
    lat = SchemaNode(Float(), missing=None)
    lon = SchemaNode(Float(), missing=None)

    time = SchemaNode(String(), missing='')
    accuracy = SchemaNode(Integer(), missing=0)
    altitude = SchemaNode(Integer(), missing=0)
    altitude_accuracy = SchemaNode(Integer(), missing=0)
    radio = SchemaNode(String(),
                       validator=OneOf(RADIO_TYPE_KEYS), missing=None)

    heading = SchemaNode(Float(), missing=-1.0)
    speed = SchemaNode(Float(), missing=-1.0)


class ReportSchema(BaseReportSchema):
    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())


class ReportsSchema(SequenceSchema):
    report = ReportSchema()


class SubmitSchema(MappingSchema):
    items = ReportsSchema()
