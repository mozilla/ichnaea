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


class CellAreaLookup(CellAreaKeyMixin, CellSignalMixin, ValidationMixin):

    _hashkey_cls = CellAreaKey
    _valid_schema = ValidCellAreaLookupSchema


class ValidCellLookupSchema(ValidCellKeySchema, ValidCellSignalSchema):
    """A schema which validates the fields in a cell lookup."""


class CellLookup(CellKeyPscMixin, CellSignalMixin, ValidationMixin):

    _hashkey_cls = CellKey
    _valid_schema = ValidCellLookupSchema


class ValidWifiLookupSchema(ValidWifiKeySchema, ValidWifiSignalSchema):
    """A schema which validates the fields in a wifi lookup."""


class WifiLookup(WifiKeyMixin, WifiSignalMixin, ValidationMixin):

    _valid_schema = ValidWifiLookupSchema
