import operator

import colander

from ichnaea.geocode import GEOCODER
from ichnaea.models.base import (
    CreationMixin,
    ValidationMixin,
)
from ichnaea.models.cell import (
    decode_radio_dict,
    encode_radio_dict,
    encode_cellid,
    CellHashKey,
    ValidCellKeySchema,
    ValidCellSignalSchema,
)
from ichnaea.models import constants
from ichnaea.models.hashkey import (
    HashKey,
    HashKeyMixin,
)
from ichnaea.models.schema import (
    DefaultNode,
    MacNode,
    ValidatorNode,
)
from ichnaea.models.wifi import (
    ValidWifiSignalSchema,
)


class CellKeyPsc(CellHashKey):

    _fields = ('radio', 'mcc', 'mnc', 'lac', 'cid', 'psc')


class WifiKey(HashKey):

    _fields = ('key', )


class ValidReportSchema(colander.MappingSchema, ValidatorNode):
    """A schema which validates the fields present in a report."""

    lat = colander.SchemaNode(
        colander.Float(), missing=None, validator=colander.Range(
            constants.MIN_LAT, constants.MAX_LAT))
    lon = colander.SchemaNode(
        colander.Float(), missing=None, validator=colander.Range(
            constants.MIN_LON, constants.MAX_LON))
    accuracy = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            0.0, constants.MAX_ACCURACY))
    altitude = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            constants.MIN_ALTITUDE, constants.MAX_ALTITUDE))
    altitude_accuracy = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            0.0, constants.MAX_ALTITUDE_ACCURACY))
    heading = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            0.0, constants.MAX_HEADING))
    speed = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            0.0, constants.MAX_SPEED))

    def validator(self, node, cstruct):
        super(ValidReportSchema, self).validator(node, cstruct)
        for field in ('lat', 'lon'):
            if (cstruct[field] is None or
                    cstruct[field] is colander.null):  # pragma: no cover
                raise colander.Invalid(node, 'Report %s is required.' % field)

        if not GEOCODER.any_region(cstruct['lat'], cstruct['lon']):
            raise colander.Invalid(node, (
                'Lat/lon must be inside a region.'))


class Report(HashKey, CreationMixin, ValidationMixin):

    _valid_schema = ValidReportSchema()
    _fields = (
        'lat',
        'lon',
        'accuracy',
        'altitude',
        'altitude_accuracy',
        'heading',
        'speed',
    )

    def _to_json_value(self):
        # create a sparse representation of this instance
        dct = {}
        for field in self._fields:
            value = getattr(self, field, None)
            if value is not None:
                dct[field] = value
        return dct

    @classmethod
    def combine(cls, *reports):
        values = {}
        for report in reports:
            values.update(report.__dict__)
        return cls(**values)


class ValidCellReportSchema(ValidCellKeySchema, ValidCellSignalSchema):
    """A schema which validates the cell specific fields in a report."""

    def validator(self, node, cstruct):
        super(ValidCellReportSchema, self).validator(node, cstruct)
        for field in ('radio', 'mcc', 'mnc', 'lac', 'cid'):
            if (cstruct[field] is None or
                    cstruct[field] is colander.null):
                raise colander.Invalid(node, 'Cell %s is required.' % field)


class CellReport(HashKey, HashKeyMixin, CreationMixin, ValidationMixin):

    _hashkey_cls = CellKeyPsc
    _valid_schema = ValidCellReportSchema()
    _fields = (
        'radio',
        'mcc',
        'mnc',
        'lac',
        'cid',
        'psc',
        'asu',
        'signal',
        'ta',
    )

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

    @property
    def cellid(self):
        return encode_cellid(
            self.radio, self.mcc, self.mnc, self.lac, self.cid)

    @classmethod
    def _from_json_value(cls, value):
        value = decode_radio_dict(value)
        return super(CellReport, cls)._from_json_value(value)

    def _to_json_value(self):
        dct = super(CellReport, self)._to_json_value()
        dct = encode_radio_dict(dct)
        return dct


class ValidCellObservationSchema(ValidCellReportSchema, ValidReportSchema):
    """A schema which validates the fields present in a cell observation."""

    def validator(self, node, cstruct):
        super(ValidCellObservationSchema, self).validator(node, cstruct)

        in_region = GEOCODER.in_region_mcc(
            cstruct['lat'], cstruct['lon'], cstruct['mcc'])

        if not in_region:
            raise colander.Invalid(node, (
                'Lat/lon must be inside one of the regions for the MCC'))


class CellObservation(CellReport, Report):

    _valid_schema = ValidCellObservationSchema()
    _fields = CellReport._fields + Report._fields


class ValidWifiReportSchema(ValidWifiSignalSchema):
    """A schema which validates the wifi specific fields in a report."""

    key = MacNode(colander.String())

    def validator(self, node, cstruct):
        super(ValidWifiReportSchema, self).validator(node, cstruct)
        if (cstruct['key'] is None or
                cstruct['key'] is colander.null):  # pragma: no cover
            raise colander.Invalid(node, 'Wifi mac address is required.')


class WifiReport(HashKey, HashKeyMixin, CreationMixin, ValidationMixin):

    _hashkey_cls = WifiKey
    _valid_schema = ValidWifiReportSchema()
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

    @property
    def mac(self):
        # BBB: alias
        return self.key


class ValidWifiObservationSchema(ValidWifiReportSchema, ValidReportSchema):
    """A schema which validates the fields in wifi observation."""


class WifiObservation(WifiReport, Report):

    _valid_schema = ValidWifiObservationSchema()
    _fields = WifiReport._fields + Report._fields
