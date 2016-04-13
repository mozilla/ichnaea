import math
import operator

import colander

from ichnaea.geocode import GEOCODER
from ichnaea.models import (
    Radio,
    ReportSource,
)
from ichnaea.models.base import (
    CreationMixin,
    ValidationMixin,
)
from ichnaea.models.blue import (
    BlueShard,
    ValidBlueSignalSchema,
)
from ichnaea.models.cell import (
    CellShard,
    encode_cellid,
    ValidCellKeySchema,
    ValidCellSignalSchema,
)
from ichnaea.models import constants
from ichnaea.models.base import (
    HashableDict,
)
from ichnaea.models.mac import MacNode
from ichnaea.models.schema import (
    DefaultNode,
    ReportSourceNode,
    ReportSourceType,
    ValidatorNode,
)

from ichnaea.models.wifi import (
    ValidWifiSignalSchema,
    WifiShard,
)


class BaseReport(HashableDict, CreationMixin, ValidationMixin):
    """A base class for reports."""

    _comparators = ()

    def better(self, other):
        """Is self better than the other?"""
        for field, better_than in self._comparators:
            old_value = getattr(self, field, None)
            new_value = getattr(other, field, None)
            if (None not in (old_value, new_value) and
                    better_than(old_value, new_value)):
                return True
        return False


class BaseObservation(object):
    """A base class for observations."""

    @classmethod
    def _from_json_value(cls, dct):
        if 'source' in dct and dct['source'] is not None and \
           not type(dct['source']) == ReportSource:
            dct['source'] = ReportSource(dct['source'])
        return cls(**dct)

    @classmethod
    def from_json(cls, dct):
        return cls._from_json_value(dct)

    def _to_json_value(self):
        # create a sparse representation of this instance
        dct = {}
        for field in self._fields:
            value = getattr(self, field, None)
            if value is not None:
                if field == 'source' and type(value) == ReportSource:
                    dct[field] = int(value)
                else:
                    dct[field] = value
        return dct

    def to_json(self):
        return self._to_json_value()


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
            constants.MIN_ACCURACY, constants.MAX_ACCURACY))
    altitude = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            constants.MIN_ALTITUDE, constants.MAX_ALTITUDE))
    altitude_accuracy = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            constants.MIN_ALTITUDE_ACCURACY, constants.MAX_ALTITUDE_ACCURACY))
    heading = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            constants.MIN_HEADING, constants.MAX_HEADING))
    pressure = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            constants.MIN_PRESSURE, constants.MAX_PRESSURE))
    source = ReportSourceNode(ReportSourceType(), missing=None)
    speed = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            constants.MIN_SPEED, constants.MAX_SPEED))
    timestamp = DefaultNode(
        colander.Integer(), missing=None, validator=colander.Range(
            constants.MIN_TIMESTAMP, constants.MAX_TIMESTAMP))

    def validator(self, node, cstruct):
        super(ValidReportSchema, self).validator(node, cstruct)
        for field in ('lat', 'lon'):
            if (cstruct[field] is None or
                    cstruct[field] is colander.null):
                raise colander.Invalid(node, 'Report %s is required.' % field)

        if not GEOCODER.any_region(cstruct['lat'], cstruct['lon']):
            raise colander.Invalid(node, 'Lat/lon must be inside a region.')


class Report(BaseReport):
    """A class for report data."""

    _valid_schema = ValidReportSchema()
    _fields = (
        'lat',
        'lon',
        'accuracy',
        'altitude',
        'altitude_accuracy',
        'heading',
        'pressure',
        'speed',
        'source',
        'timestamp',
    )

    @classmethod
    def combine(cls, *reports):
        values = {}
        for report in reports:
            values.update(report.__dict__)
        return cls(**values)

    @property
    def accuracy_weight(self):
        # Default to 10.0 meters for unknown accuracy
        accuracy = self.accuracy is not None and self.accuracy or 10.0
        # Don't differentiate values below 10 meters
        # Maps 10: 1, 20: 0.7, 40: 0.5, 80: 0.35, 100: 0.32, 200: 0.22
        return math.sqrt(10 / max(accuracy, 10.0))


class ValidBlueReportSchema(ValidBlueSignalSchema):
    """A schema which validates the Bluetooth specific fields in a report."""

    mac = MacNode(colander.String())


class BlueReport(BaseReport):
    """A class for Bluetooth report data."""

    _valid_schema = ValidBlueReportSchema()
    _fields = (
        'mac',
        'age',
        'signal',
    )
    _comparators = (
        ('signal', operator.gt),
        ('age', operator.lt),
    )

    @property
    def unique_key(self):
        return self.mac

    @property
    def shard_id(self):
        return BlueShard.shard_id(self.mac)

    @property
    def shard_model(self):
        return BlueShard.shard_model(self.mac)


class ValidBlueObservationSchema(ValidBlueReportSchema, ValidReportSchema):
    """A schema which validates the fields in a Bluetooth observation."""


class BlueObservation(BlueReport, Report, BaseObservation):
    """A class for Bluetooth observation data."""

    _valid_schema = ValidBlueObservationSchema()
    _fields = BlueReport._fields + Report._fields

    @property
    def weight(self):
        signal_weight = 1.0
        return signal_weight * self.accuracy_weight


class ValidCellReportSchema(ValidCellKeySchema, ValidCellSignalSchema):
    """A schema which validates the cell specific fields in a report."""

    def validator(self, node, cstruct):
        super(ValidCellReportSchema, self).validator(node, cstruct)
        for field in ('radio', 'mcc', 'mnc', 'lac', 'cid'):
            if (cstruct[field] is None or
                    cstruct[field] is colander.null):
                raise colander.Invalid(node, 'Cell %s is required.' % field)


class CellReport(BaseReport):
    """A class for cell report data."""

    _valid_schema = ValidCellReportSchema()
    _fields = (
        'radio',
        'mcc',
        'mnc',
        'lac',
        'cid',
        'psc',
        'age',
        'asu',
        'signal',
        'ta',
    )
    _comparators = (
        ('ta', operator.lt),
        ('signal', operator.gt),
        ('asu', operator.gt),
        ('age', operator.lt),
    )

    @property
    def unique_key(self):
        return self.cellid

    @property
    def shard_id(self):
        return CellShard.shard_id(self.cellid)

    @property
    def shard_model(self):
        return CellShard.shard_model(self.cellid)

    @property
    def cellid(self):
        return encode_cellid(
            self.radio, self.mcc, self.mnc, self.lac, self.cid)


class ValidCellObservationSchema(ValidCellReportSchema, ValidReportSchema):
    """A schema which validates the fields present in a cell observation."""

    def validator(self, node, cstruct):
        super(ValidCellObservationSchema, self).validator(node, cstruct)

        in_region = GEOCODER.in_region_mcc(
            cstruct['lat'], cstruct['lon'], cstruct['mcc'])

        if not in_region:
            raise colander.Invalid(node, (
                'Lat/lon must be inside one of the regions for the MCC'))


class CellObservation(CellReport, Report, BaseObservation):
    """A class for cell observation data."""

    _valid_schema = ValidCellObservationSchema()
    _fields = CellReport._fields + Report._fields

    @classmethod
    def _from_json_value(cls, dct):
        if 'radio' in dct and dct['radio'] is not None and \
           not type(dct['radio']) == Radio:
            dct['radio'] = Radio(dct['radio'])
        return super(CellObservation, cls)._from_json_value(dct)

    def _to_json_value(self):
        dct = super(CellObservation, self)._to_json_value()
        if 'radio' in dct and type(dct['radio']) == Radio:
            dct['radio'] = int(dct['radio'])
        return dct

    @property
    def weight(self):
        offsets = {
            # GSM median signal is -95
            # Map -113: 0.52, -95: 1.0, -79: 2.0, -51: 10.2
            Radio.gsm: (-95, -5.0),
            # WCDMA median signal is -100
            # Map -121: 0.47, -100: 1.0, -80: 2.4, -50: 16, -25: 256
            Radio.wcdma: (-100, 0.0),
            # LTE median signal is -105
            # Map -140: 0.3, -105: 1.0, -89: 2.0, -55: 16.0, -43: 48.0
            Radio.lte: (-105, 5.0),
        }
        default, offset = offsets.get(self.radio, (None, 0.0))
        signal = self.signal if self.signal is not None else default
        signal_weight = 1.0
        if signal is not None:
            signal_weight = ((1.0 / (signal + offset) ** 2) * 10000) ** 2
        return signal_weight * self.accuracy_weight


class ValidWifiReportSchema(ValidWifiSignalSchema):
    """A schema which validates the wifi specific fields in a report."""

    mac = MacNode(colander.String())


class WifiReport(BaseReport):
    """A class for wifi report data."""

    _valid_schema = ValidWifiReportSchema()
    _fields = (
        'mac',
        'age',
        'channel',
        'signal',
        'snr',
    )
    _comparators = (
        ('signal', operator.gt),
        ('snr', operator.gt),
        ('age', operator.lt),
    )

    @property
    def unique_key(self):
        return self.mac

    @property
    def shard_id(self):
        return WifiShard.shard_id(self.mac)

    @property
    def shard_model(self):
        return WifiShard.shard_model(self.mac)


class ValidWifiObservationSchema(ValidWifiReportSchema, ValidReportSchema):
    """A schema which validates the fields in wifi observation."""


class WifiObservation(WifiReport, Report, BaseObservation):
    """A class for wifi observation data."""

    _valid_schema = ValidWifiObservationSchema()
    _fields = WifiReport._fields + Report._fields

    @property
    def weight(self):
        # Default to -80 dBm for unknown signal strength
        signal = self.signal if self.signal is not None else -80
        # Maps -100: ~0.5, -80: 1.0, -60: 2.4, -30: 16, -10: ~123
        signal_weight = ((1.0 / (signal - 20.0) ** 2) * 10000) ** 2
        return signal_weight * self.accuracy_weight
