"""
General locate specific colander schemata describing the public HTTP APIs.
"""

import colander

from ichnaea.api.schema import InternalMapping
from ichnaea.models.base import ValidationMixin
from ichnaea.models.cell import (
    CellAreaKey,
    CellAreaKeyMixin,
    CellKey,
    CellKeyPscMixin,
    CellSignalMixin,
    ValidCellAreaKeySchema,
    ValidCellKeySchema,
    ValidCellSignalSchema,
)
from ichnaea.models.wifi import (
    ValidWifiKeySchema,
    ValidWifiSignalSchema,
    WifiKeyMixin,
    WifiSignalMixin,
)


class ValidCellAreaLookupSchema(ValidCellAreaKeySchema, ValidCellSignalSchema):
    """A schema which validates the fields in a cell area lookup."""

    def validator(self, schema, data):
        super(ValidCellAreaLookupSchema, self).validator(schema, data)
        if data['lac'] is None:
            raise colander.Invalid(schema, ('LAC is required in lookups.'))


class CellAreaLookup(CellAreaKeyMixin, CellSignalMixin, ValidationMixin):

    _hashkey_cls = CellAreaKey
    _valid_schema = ValidCellAreaLookupSchema


class ValidCellLookupSchema(ValidCellKeySchema, ValidCellSignalSchema):
    """A schema which validates the fields in a cell lookup."""

    def validator(self, schema, data):
        super(ValidCellLookupSchema, self).validator(schema, data)
        if data['cid'] is None:
            raise colander.Invalid(schema, ('CID is required in lookups.'))


class CellLookup(CellKeyPscMixin, CellSignalMixin, ValidationMixin):

    _hashkey_cls = CellKey
    _valid_schema = ValidCellLookupSchema


class ValidWifiLookupSchema(ValidWifiKeySchema, ValidWifiSignalSchema):
    """A schema which validates the fields in a wifi lookup."""


class WifiLookup(WifiKeyMixin, WifiSignalMixin, ValidationMixin):

    _valid_schema = ValidWifiLookupSchema


class BaseLocateSchema(colander.MappingSchema):
    schema_type = InternalMapping

    def deserialize(self, data):
        data = super(BaseLocateSchema, self).deserialize(data)

        if 'radio' in data:
            radio = data.get('radio', None)
            for cell in data.get('cell', ()):
                if 'radio' not in cell:
                    cell['radio'] = radio

            del data['radio']

        return data
