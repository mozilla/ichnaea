"""
General locate specific colander schemata describing the public HTTP APIs.
"""

import operator

import colander

from ichnaea.api.schema import RenamingMappingSchema
from ichnaea.models.base import (
    CreationMixin,
    HashableDict,
    ValidationMixin,
)
from ichnaea.models.cell import (
    encode_cellarea,
    encode_cellid,
    ValidCellAreaKeySchema,
    ValidCellKeySchema,
)
from ichnaea.models import constants
from ichnaea.models.constants import Radio
from ichnaea.models.mac import (
    encode_mac,
    MacNode,
)
from ichnaea.models.schema import (
    DefaultNode,
    ValidatorNode,
)


class BaseLookup(HashableDict, CreationMixin, ValidationMixin):
    """A base class for lookup models."""

    _valid_schema = None  #:
    _fields = ()  #:
    _comparators = ()  #:

    def better(self, other):
        """Is self better than the other?"""
        for field, better_than in self._comparators:
            old_value = getattr(self, field, None)
            new_value = getattr(other, field, None)
            if (None not in (old_value, new_value) and
                    better_than(old_value, new_value)):
                return True
        return False


class ValidBlueLookupSchema(colander.MappingSchema, ValidatorNode):
    """A schema which validates the fields in a Bluetooth lookup."""

    macAddress = MacNode(colander.String())
    name = DefaultNode(colander.String(), missing=None)

    age = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(
            constants.MIN_AGE, constants.MAX_AGE))

    signalStrength = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(
            constants.MIN_BLUE_SIGNAL, constants.MAX_BLUE_SIGNAL))


class BlueLookup(BaseLookup):
    """A model class representing a Bluetooth lookup."""

    _valid_schema = ValidBlueLookupSchema()
    _fields = (
        'macAddress',
        'age',
        'signalStrength',
        'name',
    )
    _comparators = (
        ('signalStrength', operator.gt),
        ('age', operator.lt),
    )

    @property
    def mac(self):
        return encode_mac(self.macAddress)


class BaseCellLookup(BaseLookup):
    """A base class for cell related lookup models."""

    _key_fields = (
        'radio',
        'mcc',
        'mnc',
        'lac',
    )  #:
    _signal_fields = (
        'age',
        'asu',
        'signalStrength',
        'timingAdvance',
    )  #:
    _fields = _key_fields + _signal_fields  #:

    _comparators = (
        ('timingAdvance', operator.lt),
        ('signalStrength', operator.gt),
        ('asu', operator.gt),
        ('age', operator.lt),
    )

    @property
    def areaid(self):
        return encode_cellarea(self.radio, self.mcc, self.mnc, self.lac)

    def better(self, other):
        """Is self better than the other?"""
        comparators = [
            ('timingAdvance', operator.lt),
            ('signalStrength', operator.gt),
            ('asu', operator.gt),
            ('age', operator.lt),
        ]
        for field, better_than in comparators:
            old_value = getattr(self, field, None)
            new_value = getattr(other, field, None)
            if (None not in (old_value, new_value) and
                    better_than(old_value, new_value)):
                return True
        return False


class ValidCellSignalSchema(colander.MappingSchema, ValidatorNode):

    age = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(
            constants.MIN_AGE, constants.MAX_AGE))

    asu = DefaultNode(
        colander.Integer(),
        missing=None, validator=colander.Range(
            min(constants.MIN_CELL_ASU.values()),
            max(constants.MAX_CELL_ASU.values())))

    signalStrength = DefaultNode(
        colander.Integer(),
        missing=None, validator=colander.Range(
            min(constants.MIN_CELL_SIGNAL.values()),
            max(constants.MAX_CELL_SIGNAL.values())))

    timingAdvance = DefaultNode(
        colander.Integer(),
        missing=None, validator=colander.Range(
            constants.MIN_CELL_TA, constants.MAX_CELL_TA))

    def _signal_from_asu(self, radio, value):
        if radio is Radio.gsm:
            return (value * 2) - 113
        if radio is Radio.wcdma:
            return value - 116
        if radio is Radio.lte:
            return value - 140

    def deserialize(self, data):
        if data:
            # Sometimes the asu and signal fields are swapped
            if (data.get('asu') is not None and
                    data.get('asu', 0) < -5 and
                    (data.get('signalStrength') is None or
                     data.get('signalStrength', 0) >= 0)):
                # shallow copy
                data = dict(data)
                data['signalStrength'] = data['asu']
                data['asu'] = None

        data = super(ValidCellSignalSchema, self).deserialize(data)

        if isinstance(data.get('radio'), Radio):
            radio = data['radio']

            # Radio type specific checks for ASU field
            if data.get('asu') is not None:
                if not (constants.MIN_CELL_ASU[radio] <=
                        data['asu'] <=
                        constants.MAX_CELL_ASU[radio]):
                    data = dict(data)
                    data['asu'] = None

            # Radio type specific checks for signal field
            if data.get('signalStrength') is not None:
                if not (constants.MIN_CELL_SIGNAL[radio] <=
                        data['signalStrength'] <=
                        constants.MAX_CELL_SIGNAL[radio]):
                    data = dict(data)
                    data['signalStrength'] = None

            # Radio type specific checks for TA field
            if data.get('timingAdvance') is not None and radio is Radio.wcdma:
                data = dict(data)
                data['timingAdvance'] = None

            # Calculate signal from ASU field
            if (data.get('asu') is not None and
                    data.get('signalStrength') is None):
                if (constants.MIN_CELL_ASU[radio] <= data['asu'] <=
                        constants.MAX_CELL_ASU[radio]):
                    data = dict(data)
                    data['signalStrength'] = self._signal_from_asu(
                        radio, data['asu'])

        return data


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


class ValidWifiLookupSchema(colander.MappingSchema, ValidatorNode):
    """A schema which validates the fields in a WiFi lookup."""

    macAddress = MacNode(colander.String())
    ssid = DefaultNode(colander.String(), missing=None)

    age = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(
            constants.MIN_AGE, constants.MAX_AGE))

    channel = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(
            constants.MIN_WIFI_CHANNEL, constants.MAX_WIFI_CHANNEL))

    signalStrength = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(
            constants.MIN_WIFI_SIGNAL, constants.MAX_WIFI_SIGNAL))

    signalToNoiseRatio = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(
            constants.MIN_WIFI_SNR, constants.MAX_WIFI_SNR))

    def deserialize(self, data):
        if data:
            channel = data.get('channel')
            channel = channel is not None and int(channel) or None

            if (channel is None or not
                    (constants.MIN_WIFI_CHANNEL <= channel <=
                     constants.MAX_WIFI_CHANNEL)):
                # shallow copy
                data = dict(data)

                # if no explicit channel was given, calculate
                freq = data.get('frequency', None)
                if freq is None:
                    freq = 0

                if 2411 < freq < 2473:
                    # 2.4 GHz band
                    data['channel'] = (freq - 2407) // 5
                elif freq == 2484:
                    data['channel'] = 14
                elif 5169 < freq < 5826:
                    # 5 GHz band
                    data['channel'] = (freq - 5000) // 5
                else:
                    data['channel'] = None

        return super(ValidWifiLookupSchema, self).deserialize(data)


class WifiLookup(BaseLookup):
    """A model class representing a WiFi lookup."""

    _valid_schema = ValidWifiLookupSchema()
    _fields = (
        'macAddress',
        'age',
        'channel',
        'signalStrength',
        'signalToNoiseRatio',
        'ssid',
    )
    _comparators = (
        ('signalStrength', operator.gt),
        ('signalToNoiseRatio', operator.gt),
        ('age', operator.lt),
    )

    @property
    def mac(self):
        return encode_mac(self.macAddress)


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
            for cell in data.get('cellTowers', ()):
                if 'radio' not in cell or not cell['radio']:
                    cell['radio'] = data['radio']

            del data['radio']

        return data
