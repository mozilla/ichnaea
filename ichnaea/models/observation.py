import operator

import colander
import mobile_codes

from ichnaea import geocalc
from ichnaea.models.base import (
    CreationMixin,
    ValidationMixin,
    ValidPositionSchema,
)
from ichnaea.models.cell import (
    decode_radio_dict,
    encode_radio_dict,
    CellKeyPsc,
    ValidCellKeySchema,
    ValidCellSignalSchema,
)
from ichnaea.models import constants
from ichnaea.models.hashkey import (
    HashKey,
    HashKeyMixin,
)
from ichnaea.models.schema import (
    DateTimeFromString,
    DefaultNode,
    normalized_time,
)
from ichnaea.models.wifi import (
    WifiKey,
    ValidWifiKeySchema,
    ValidWifiSignalSchema,
)


class RoundToMonthDateNode(colander.SchemaNode):
    """
    A node which takes a string date or date and
    rounds it to the first of the month.
    ex: 2015-01-01
    """

    def preparer(self, cstruct):
        return normalized_time(cstruct)


class ValidReportSchema(ValidPositionSchema):
    """A schema which validates the fields present in a report."""

    accuracy = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            0, constants.MAX_ACCURACY))
    altitude = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            constants.MIN_ALTITUDE, constants.MAX_ALTITUDE))
    altitude_accuracy = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            0, constants.MAX_ALTITUDE_ACCURACY))
    heading = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            0, constants.MAX_HEADING))
    speed = DefaultNode(
        colander.Float(), missing=None, validator=colander.Range(
            0, constants.MAX_SPEED))
    created = colander.SchemaNode(DateTimeFromString(), missing=None)
    time = RoundToMonthDateNode(DateTimeFromString(), missing=None)


class Report(HashKey, CreationMixin, ValidationMixin):

    _valid_schema = ValidReportSchema
    _fields = (
        'lat',
        'lon',
        'created',  # the insertion time
        'time',  # the time of observation
        'accuracy',
        'altitude',
        'altitude_accuracy',
        'heading',
        'speed',
    )


class ObservationMixin(Report):

    _fields = (
        'id',
    ) + Report._fields

    def _to_json_value(self):
        # create a sparse representation of this instance
        dct = {}
        for field in self._fields:
            value = getattr(self, field, None)
            if value is not None:
                dct[field] = value
        return dct


class ValidCellReportSchema(ValidCellKeySchema, ValidCellSignalSchema):
    """A schema which validates the cell specific fields in a report."""


class CellReport(HashKey, HashKeyMixin, CreationMixin, ValidationMixin):

    _hashkey_cls = CellKeyPsc
    _valid_schema = ValidCellReportSchema
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

    @classmethod
    def better_data(cls, new, old):
        comparators = [
            ('ta', operator.lt),
            ('signal', operator.gt),
            ('asu', operator.gt),
        ]
        for field, better in comparators:
            if (None not in (old[field], new[field]) and
                    better(new[field], old[field])):
                return True
        return False

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

    def validator(self, schema, data):
        super(ValidCellObservationSchema, self).validator(schema, data)

        in_country = False
        for code in mobile_codes.mcc(str(data['mcc'])):
            in_country = in_country or geocalc.location_is_in_country(
                data['lat'], data['lon'], code.alpha2, 1)

        if not in_country:
            raise colander.Invalid(schema, (
                'Lat/lon must be inside one of '
                'the bounding boxes for the MCC'))


class CellObservation(CellReport, ObservationMixin):

    _valid_schema = ValidCellObservationSchema
    _fields = CellReport._fields + ObservationMixin._fields


class ValidWifiReportSchema(ValidWifiKeySchema, ValidWifiSignalSchema):
    """A schema which validates the wifi specific fields in a report."""


class WifiReport(HashKey, HashKeyMixin, CreationMixin, ValidationMixin):

    _hashkey_cls = WifiKey
    _valid_schema = ValidWifiReportSchema
    _fields = (
        'key',
        'channel',
        'signal',
        'snr',
    )

    @classmethod
    def better_data(cls, new, old):
        if (None not in (old['signal'], new['signal']) and
                new['signal'] > old['signal']):
            return True
        return False


class ValidWifiObservationSchema(ValidWifiReportSchema, ValidReportSchema):
    """A schema which validates the fields in wifi observation."""


class WifiObservation(WifiReport, ObservationMixin):

    _valid_schema = ValidWifiObservationSchema
    _fields = WifiReport._fields + ObservationMixin._fields
