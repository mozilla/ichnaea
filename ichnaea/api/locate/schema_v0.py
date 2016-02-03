"""
Colander schemata describing the public v1/search HTTP API.
"""

import colander

from ichnaea.api.schema import RenamingMappingSchema
from ichnaea.api.locate.schema import (
    BaseLocateSchema,
    FallbackSchema,
)


RADIO_STRINGS = ['gsm', 'cdma', 'umts', 'wcdma', 'lte']


class BluesSchema(colander.SequenceSchema):

    @colander.instantiate()
    class SequenceItem(RenamingMappingSchema):

        key = colander.SchemaNode(
            colander.String(), missing=None, to_name='mac')
        signal = colander.SchemaNode(colander.Integer(), missing=None)
        name = colander.SchemaNode(colander.String(), missing=None)


class CellsSchema(colander.SequenceSchema):

    @colander.instantiate()
    class SequenceItem(RenamingMappingSchema):

        radio = colander.SchemaNode(
            colander.String(),
            validator=colander.OneOf(RADIO_STRINGS), missing=None)
        mcc = colander.SchemaNode(colander.Integer(), missing=None)
        mnc = colander.SchemaNode(colander.Integer(), missing=None)
        lac = colander.SchemaNode(colander.Integer(), missing=None)
        cid = colander.SchemaNode(colander.Integer(), missing=None)

        asu = colander.SchemaNode(colander.Integer(), missing=None)
        psc = colander.SchemaNode(colander.Integer(), missing=None)
        signal = colander.SchemaNode(colander.Integer(), missing=None)
        ta = colander.SchemaNode(colander.Integer(), missing=None)


class WifisSchema(colander.SequenceSchema):

    @colander.instantiate()
    class SequenceItem(RenamingMappingSchema):

        key = colander.SchemaNode(
            colander.String(), missing=None, to_name='mac')
        frequency = colander.SchemaNode(colander.Integer(), missing=None)
        channel = colander.SchemaNode(colander.Integer(), missing=None)
        signal = colander.SchemaNode(colander.Integer(), missing=None)
        signalToNoiseRatio = colander.SchemaNode(
            colander.Integer(), missing=None, to_name='snr')
        ssid = colander.SchemaNode(colander.String(), missing=None)


class LocateV0Schema(BaseLocateSchema):

    radio = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(RADIO_STRINGS), missing=None)
    blue = BluesSchema(missing=())
    cell = CellsSchema(missing=())
    wifi = WifisSchema(missing=())
    fallbacks = FallbackSchema(missing=None)

LOCATE_V0_SCHEMA = LocateV0Schema()
