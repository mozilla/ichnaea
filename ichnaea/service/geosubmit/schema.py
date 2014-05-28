# This API is based on both the Google geolocation API (link to
# business stuff) and the W3C geolocation position interface
# (http://www.w3.org/TR/geolocation-API/#position_interface)

from ichnaea.decimaljson import (
    EXPONENT_STR,
)

from colander import (
    Decimal,
    Integer,
    MappingSchema,
    OneOf,
    SchemaNode,
    String,
)

from ichnaea.service.geolocate.schema import (
    CellTowersSchema,
    WifiAccessPointsSchema,
)
SUBMIT_RADIO_TYPE_KEYS = ['gsm', 'cdma', 'wcdma', 'lte']


class GeoSubmitSchema(MappingSchema):
    # lat/lon being set to -255 indicates that this measure should be
    # skipped.  Other fields can be filled in with defaults
    latitude = SchemaNode(Decimal(quant=EXPONENT_STR), location="body",
                          missing=-255)
    longitude = SchemaNode(Decimal(quant=EXPONENT_STR), location="body",
                           missing=-255)
    accuracy = SchemaNode(Integer(), location="body", type='int', missing=0)

    altitude = SchemaNode(Integer(), location="body", type='int', missing=0)
    altitude_accuracy = SchemaNode(Integer(), location="body", type='int',
                                   missing=0)

    heading = SchemaNode(Decimal(quant=EXPONENT_STR), location="body",
                         missing=-255)

    speed = SchemaNode(Decimal(quant=EXPONENT_STR),
                       location="body", missing=-255)

    timestamp = SchemaNode(Decimal(quant=EXPONENT_STR),
                           location="body", missing=-255)

    # the following fields are the same as the geolocate API, with
    # the addition of the lte radio type
    homeMobileCountryCode = SchemaNode(
        Integer(), location="body", type='int', missing=0)
    homeMobileNetworkCode = SchemaNode(
        Integer(), location="body", type='int', missing=0)
    radioType = SchemaNode(String(), location="body", type='str',
                           validator=OneOf(SUBMIT_RADIO_TYPE_KEYS), missing='')
    carrier = SchemaNode(String(), location="body", missing='')

    cellTowers = CellTowersSchema(missing=())
    wifiAccessPoints = WifiAccessPointsSchema(missing=())
