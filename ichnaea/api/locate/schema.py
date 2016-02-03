"""
General locate specific colander schemata describing the public HTTP APIs.
"""

import operator

import colander

from ichnaea.api.schema import RenamingMappingSchema
from ichnaea.models.base import (
    CreationMixin,
    ValidationMixin,
)
from ichnaea.models.blue import ValidBlueSignalSchema
from ichnaea.models.cell import (
    encode_cellarea,
    encode_cellid,
    ValidCellAreaKeySchema,
    ValidCellKeySchema,
    ValidCellSignalSchema,
)
from ichnaea.models.base import HashableDict
from ichnaea.models.mac import MacNode
from ichnaea.models.schema import DefaultNode
from ichnaea.models.wifi import ValidWifiSignalSchema


class BaseLookup(HashableDict, CreationMixin, ValidationMixin):
    """A base class for lookup models."""

    _valid_schema = None  #:
    _fields = ()  #:

    def better(self, other):
        """Is self better than the other?"""
        raise NotImplementedError()


class ValidBlueLookupSchema(ValidBlueSignalSchema):
    """A schema which validates the fields in a Bluetooth lookup."""

    mac = MacNode(colander.String())
    name = DefaultNode(colander.String(), missing=None)


class BlueLookup(BaseLookup):
    """A model class representing a Bluetooth lookup."""

    _valid_schema = ValidBlueLookupSchema()
    _fields = (
        'mac',
        'signal',
        'name',
    )

    def better(self, other):
        """Is self better than the other?"""
        old_value = getattr(self, 'signal', None)
        new_value = getattr(other, 'signal', None)
        if (None not in (old_value, new_value) and
                old_value > new_value):
            return True
        return False


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

    @property
    def areaid(self):
        return encode_cellarea(self.radio, self.mcc, self.mnc, self.lac)

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

    _valid_schema = ValidCellAreaLookupSchema()
    _fields = BaseCellLookup._fields


class ValidCellLookupSchema(ValidCellKeySchema, ValidCellSignalSchema):
    """A schema which validates the fields in a cell lookup."""

    def validator(self, node, cstruct):
        super(ValidCellLookupSchema, self).validator(node, cstruct)

        if (cstruct['lac'] is None or cstruct['cid'] is None):
            raise colander.Invalid(node, ('LAC/CID are required in lookups.'))


class CellLookup(BaseCellLookup):
    """A model class representing a cell lookup."""

    _valid_schema = ValidCellLookupSchema()
    _fields = BaseCellLookup._key_fields + (
        'cid',
        'psc',
    ) + BaseCellLookup._signal_fields

    @property
    def cellid(self):
        return encode_cellid(
            self.radio, self.mcc, self.mnc, self.lac, self.cid)


class ValidWifiLookupSchema(ValidWifiSignalSchema):
    """A schema which validates the fields in a WiFi lookup."""

    mac = MacNode(colander.String())
    ssid = DefaultNode(colander.String(), missing=None)


class WifiLookup(BaseLookup):
    """A model class representing a WiFi lookup."""

    _valid_schema = ValidWifiLookupSchema()
    _fields = (
        'mac',
        'channel',
        'signal',
        'snr',
        'ssid',
    )

    def better(self, other):
        """Is self better than the other?"""
        old_value = getattr(self, 'signal', None)
        new_value = getattr(other, 'signal', None)
        if (None not in (old_value, new_value) and
                old_value > new_value):
            return True
        return False


class FallbackSchema(colander.MappingSchema):
    """
    A schema validating the fields present in fallback options.
    """

    lacf = DefaultNode(colander.Boolean(), missing=True)
    ipf = DefaultNode(colander.Boolean(), missing=True)


class FallbackLookup(HashableDict, CreationMixin, ValidationMixin):
    """A model class representing fallback lookup options."""

    _valid_schema = FallbackSchema()
    _fields = (
        'ipf',
        'lacf',
    )


class BaseLocateSchema(RenamingMappingSchema):
    """A base schema for all locate related schemata."""

    def deserialize(self, data):
        data = super(BaseLocateSchema, self).deserialize(data)

        if 'radio' in data:
            for cell in data.get('cell', ()):
                if 'radio' not in cell or not cell['radio']:
                    cell['radio'] = data['radio']

            del data['radio']

        return data
