from ichnaea.models.base import ValidationMixin
from ichnaea.models.cell import (
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


class CellAreaLookup(CellKeyPscMixin, CellSignalMixin, ValidationMixin):

    _hashkey_cls = CellKey
    _valid_schema = ValidCellAreaKeySchema


class ValidCellLookupSchema(ValidCellKeySchema, ValidCellSignalSchema):
    """A schema which validates the fields in a cell lookup."""


class CellLookup(CellAreaLookup):

    _valid_schema = ValidCellLookupSchema


class ValidWifiLookupSchema(ValidWifiKeySchema, ValidWifiSignalSchema):
    """A schema which validates the fields in a wifi lookup."""


class WifiLookup(WifiKeyMixin, WifiSignalMixin, ValidationMixin):

    _valid_schema = ValidWifiLookupSchema
