"""
General locate specific colander schemata describing the public HTTP APIs.
"""

import operator

import colander

from ichnaea.api.schema import InternalMapping
from ichnaea.models.base import (
    CreationMixin,
    ValidationMixin,
)
from ichnaea.models.cell import (
    CellAreaKey,
    CellKey,
    ValidCellAreaKeySchema,
    ValidCellKeySchema,
    ValidCellSignalSchema,
)
from ichnaea.models.hashkey import (
    HashKey,
    HashKeyMixin,
)
from ichnaea.models.wifi import (
    ValidWifiKeySchema,
    ValidWifiSignalSchema,
    WifiKey,
)


class BaseLookup(HashKey, HashKeyMixin, CreationMixin, ValidationMixin):
    """A base class for lookup models."""

    _hashkey_cls = None  #:
    _valid_schema = None  #:
    _fields = ()  #:

    def better(self, other):  # pragma: no cover
        """Is self better than the other?"""
        raise NotImplementedError()


class BaseCellLookup(BaseLookup):
    """A base class for cell related lookup models."""

    _key_fields = (
        'radio',
        'mcc',
        'mnc',
        'lac',
    )  #:
    _signal_fields = (
        'asu',
        'signal',
        'ta',
    )  #:
    _fields = _key_fields + _signal_fields  #:

    def better(self, other):
        """Is self better than the other?"""
        comparators = [
            ('ta', operator.lt),
            ('signal', operator.gt),
            ('asu', operator.gt),
        ]
        for field, better_than in comparators:
            old_value = getattr(self, field, None)
            new_value = getattr(other, field, None)
            if (None not in (old_value, new_value) and
                    better_than(old_value, new_value)):
                return True
        return False


class ValidCellAreaLookupSchema(ValidCellAreaKeySchema, ValidCellSignalSchema):
    """A schema which validates the fields in a cell area lookup."""

    def validator(self, node, cstruct):
        super(ValidCellAreaLookupSchema, self).validator(node, cstruct)

        if cstruct['lac'] is None:
            raise colander.Invalid(node, ('LAC is required in lookups.'))


class CellAreaLookup(BaseCellLookup):
    """A model class representing a cell area lookup."""

    _hashkey_cls = CellAreaKey
    _valid_schema = ValidCellAreaLookupSchema
    _fields = BaseCellLookup._fields


class ValidCellLookupSchema(ValidCellKeySchema, ValidCellSignalSchema):
    """A schema which validates the fields in a cell lookup."""

    def validator(self, node, cstruct):
        super(ValidCellLookupSchema, self).validator(node, cstruct)

        if cstruct['cid'] is None:
            raise colander.Invalid(node, ('CID is required in lookups.'))


class CellLookup(BaseCellLookup):
    """A model class representing a cell lookup."""

    _hashkey_cls = CellKey
    _valid_schema = ValidCellLookupSchema
    _fields = BaseCellLookup._key_fields + (
        'cid',
        'psc',
    ) + BaseCellLookup._signal_fields


class ValidWifiLookupSchema(ValidWifiKeySchema, ValidWifiSignalSchema):
    """A schema which validates the fields in a wifi lookup."""


class WifiLookup(BaseLookup):
    """A model class representing a cell lookup."""

    _hashkey_cls = WifiKey
    _valid_schema = ValidWifiLookupSchema
    _fields = (
        'key',
        'channel',
        'signal',
        'snr',
    )

    def better(self, other):
        """Is self better than the other?"""
        old_value = getattr(self, 'signal', None)
        new_value = getattr(other, 'signal', None)
        if (None not in (old_value, new_value) and
                old_value > new_value):
            return True
        return False


class BaseLocateSchema(colander.MappingSchema):
    """A base schema for all locate related schemata."""

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
