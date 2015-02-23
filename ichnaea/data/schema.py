import copy
from datetime import date, datetime, timedelta
import uuid

import mobile_codes
from colander import (
    Boolean,
    DateTime,
    Float,
    Integer,
    Invalid,
    MappingSchema,
    null,
    Range,
    SchemaNode,
    String,
)
import iso8601
from pytz import UTC

from ichnaea import geocalc
from ichnaea.data import constants
from ichnaea.models import Radio
from ichnaea import util


# Utility functions

def normalized_time(time):
    """
    Takes a string representation of a time value or a date and converts
    it into a datetime.

    It rounds down a date to the first of the month.

    It takes any date greater than 60 days into the past
    or in the future and sets it to the current date.
    """
    now = util.utcnow()
    if not time:
        time = now
    elif isinstance(time, (str, unicode, date)):
        try:
            time = iso8601.parse_date(time)
        except (iso8601.ParseError, TypeError):
            time = now

    # don't accept future time values or
    # time values more than 60 days in the past
    min_time = now - timedelta(days=60)
    if time > now or time < min_time:
        time = now

    # cut down the time to a monthly resolution
    time = time.replace(day=1, hour=0, minute=0, second=0,
                        microsecond=0, tzinfo=UTC)
    return time


def normalized_wifi_key(key):
    """
    Remove ':' '-' ',' from a wifi key.
    """
    if ":" in key or "-" in key or "." in key:
        key = key.replace(":", "").replace("-", "").replace(".", "")
    return key.lower()


def valid_wifi_pattern(key):
    """
    Return True if a wifi key matches our valid regex,
    our invalid regex, and has length 12.
    """
    return constants.INVALID_WIFI_REGEX.match(key) and \
        constants.VALID_WIFI_REGEX.match(key) and len(key) == 12


# Custom Types

class DateTimeFromString(DateTime):
    """
    A DateTimeFromString will return a datetime object
    from either a datetime object or a string.
    """

    def deserialize(self, schema, cstruct):
        if type(cstruct) == datetime:
            return cstruct
        return super(DateTimeFromString, self).deserialize(schema, cstruct)


class RadioType(Integer):
    """
    A RadioType will return a Radio IntEnum object.
    """

    def deserialize(self, node, cstruct):
        if cstruct is null:  # pragma: no cover
            return null
        if isinstance(cstruct, Radio):
            return cstruct
        try:
            if isinstance(cstruct, basestring):
                cstruct = Radio[cstruct]
            else:
                cstruct = Radio(cstruct)
        except (KeyError, ValueError):
            raise Invalid(node, '%r is not a valid radio type' % cstruct)
        return cstruct


class UUIDType(String):
    """
    A UUIDType will return a uuid object from either a uuid or a string.
    """

    def deserialize(self, node, cstruct):
        if not cstruct:
            return null
        if isinstance(cstruct, uuid.UUID):
            return cstruct
        try:
            cstruct = uuid.UUID(hex=cstruct)
        except (AttributeError, TypeError, ValueError):
            raise Invalid(node, '%r is not a valid hex uuid' % cstruct)
        return cstruct


# Custom Nodes

class DefaultNode(SchemaNode):
    """
    A DefaultNode will use its ``missing`` value
    if it fails to validate during deserialization.
    """

    def deserialize(self, cstruct):
        try:
            return super(DefaultNode, self).deserialize(cstruct)
        except Invalid:
            return self.missing


class WifiKeyNode(SchemaNode):
    """
    A node containing a valid wifi key.
    ex: 01005e901000
    """

    def preparer(self, cstruct):
        return normalized_wifi_key(cstruct)

    def validator(self, node, cstruct):
        if not valid_wifi_pattern(cstruct):
            raise Invalid(node, 'Invalid wifi key')


class RadioNode(DefaultNode):
    """
    A node containing a valid radio enum.
    """

    def validator(self, node, cstruct):
        if type(cstruct) == Radio:
            return True
        if cstruct is None or cstruct is null:  # pragma: no cover
            return True
        raise Invalid(node, 'Invalid radio type')  # pragma: no cover


class ReportIDNode(SchemaNode):
    """
    A node containing a valid report_id.
    ex: 489cc8dc9d3d11e4a87d02442b52e5a0
    """

    def preparer(self, cstruct):
        return cstruct or uuid.uuid1()


class RoundToMonthDateNode(SchemaNode):
    """
    A node which takes a string date or date and
    rounds it to the first of the month.
    ex: 2015-01-01
    """

    def preparer(self, cstruct):
        return normalized_time(cstruct)


# Schemas

class CopyingSchema(MappingSchema):
    """
    A Schema which makes a copy of the passed in dict to validate.
    """

    def deserialize(self, data):
        return super(CopyingSchema, self).deserialize(copy.copy(data))


class FieldSchema(MappingSchema):
    """
    A schema which provides an interface to its fields through the
    .fields[field_name] interface.
    """

    @property
    def fields(self):
        return dict([(field.name, field) for field in self.children])

    def is_missing(self, data, field_name):
        missing_value = self.fields[field_name].missing
        data_value = data.get(field_name, missing_value)
        return data_value == missing_value


class ValidPositionSchema(FieldSchema, CopyingSchema):
    """A schema which validates the fields present in a position."""

    lat = SchemaNode(Float(), missing=0.0, validator=Range(
        constants.MIN_LAT, constants.MAX_LAT))
    lon = SchemaNode(Float(), missing=0.0, validator=Range(
        constants.MIN_LON, constants.MAX_LON))


class ValidStationSchema(ValidPositionSchema):
    """A schema which validates the fields present in a station."""

    total_measures = SchemaNode(Integer(), missing=0)
    range = SchemaNode(Integer(), missing=0)


class ValidReportSchema(ValidPositionSchema):
    """A schema which validates the fields present in a report."""

    accuracy = DefaultNode(
        Float(), missing=0, validator=Range(0, constants.MAX_ACCURACY))
    altitude = DefaultNode(
        Float(), missing=0, validator=Range(
            constants.MIN_ALTITUDE, constants.MAX_ALTITUDE))
    altitude_accuracy = DefaultNode(
        Float(), missing=0, validator=Range(
            0, constants.MAX_ALTITUDE_ACCURACY))
    heading = DefaultNode(
        Float(), missing=-1, validator=Range(0, constants.MAX_HEADING))
    speed = DefaultNode(
        Float(), missing=-1, validator=Range(0, constants.MAX_SPEED))
    report_id = ReportIDNode(UUIDType())
    created = SchemaNode(DateTimeFromString(), missing=None)
    time = RoundToMonthDateNode(DateTimeFromString(), missing=None)


class ValidWifiKeySchema(FieldSchema, CopyingSchema):
    """A schema which validates the fields present in a a wifi key."""

    key = WifiKeyNode(String())


class ValidWifiSchema(ValidWifiKeySchema, ValidStationSchema):
    """A schema which validates the fields in wifi."""


class ValidWifiLookupSchema(ValidWifiKeySchema):
    """A schema which validates the fields in a wifi lookup."""

    channel = SchemaNode(Integer(), missing=0, validator=Range(
        constants.MIN_WIFI_CHANNEL, constants.MAX_WIFI_CHANNEL))
    signal = DefaultNode(Integer(), missing=0, validator=Range(
        constants.MIN_WIFI_SIGNAL, constants.MAX_WIFI_SIGNAL))
    snr = DefaultNode(Integer(), missing=0, validator=Range(0, 100))

    def deserialize(self, data):
        if data:
            channel = int(data.get('channel', 0))

            if not (constants.MIN_WIFI_CHANNEL
                    < channel
                    < constants.MAX_WIFI_CHANNEL):
                # if no explicit channel was given, calculate
                freq = data.get('frequency', 0)

                if 2411 < freq < 2473:
                    # 2.4 GHz band
                    data['channel'] = (freq - 2407) // 5

                elif 5169 < freq < 5826:
                    # 5 GHz band
                    data['channel'] = (freq - 5000) // 5

                else:
                    data['channel'] = self.fields['channel'].missing

            # map external name to internal
            if data.get('snr', None) is None:
                data['snr'] = data.get('signalToNoiseRatio', 0)

        return super(ValidWifiKeySchema, self).deserialize(data)


class ValidWifiObservationSchema(ValidWifiLookupSchema, ValidReportSchema):
    """A schema which validates the fields in wifi observation."""


class ValidWifiReportSchema(ValidWifiLookupSchema):
    """A schema which validates the wifi specific fields in a report."""


class ValidCellKeySchema(FieldSchema, CopyingSchema):
    """A schema which validates the fields present in a cell key."""

    cid = DefaultNode(
        Integer(), missing=0, validator=Range(
            constants.MIN_CID, constants.MAX_CID_ALL))
    lac = DefaultNode(
        Integer(), missing=0, validator=Range(
            constants.MIN_LAC, constants.MAX_LAC_ALL))
    mcc = SchemaNode(Integer(), validator=Range(1, 999))
    mnc = SchemaNode(Integer(), validator=Range(0, 32767))
    psc = DefaultNode(Integer(), missing=-1, validator=Range(0, 512))
    radio = RadioNode(RadioType(), missing=None)

    def deserialize(self, data, default_radio=None):
        if data:
            # deserialize radio child field early
            data['radio'] = self.fields['radio'].deserialize(data['radio'])

            # If a default radio was set,
            # and we don't know, use it as fallback
            if (self.is_missing(data, 'radio')
                    and default_radio is not None):
                data['radio'] = self.fields['radio'].deserialize(default_radio)

            # If the cell id >= 65536 then it must be a umts tower
            if (data.get('cid', 0) >= 65536
                    and data['radio'] == Radio.gsm):
                data['radio'] = Radio.umts

            # Treat cid=65535 without a valid lac as an unspecified value
            if (self.is_missing(data, 'lac')
                    and data.get('cid', None) == 65535):
                data['cid'] = self.fields['cid'].missing

        return super(ValidCellKeySchema, self).deserialize(data)

    def validator(self, schema, data):
        lac_missing = self.is_missing(data, 'lac')
        cid_missing = self.is_missing(data, 'cid')

        if data['mcc'] not in constants.ALL_VALID_MCCS:
            raise Invalid(
                schema, 'Check against the list of all known valid mccs')

        if (data['radio'] == Radio.cdma
                and (lac_missing or cid_missing)):
            raise Invalid(schema, (
                'Skip CDMA towers missing lac or cid '
                '(no psc on CDMA exists to backfill using inference)'))

        if data['radio'] in Radio._gsm_family() and data['mnc'] > 999:
            raise Invalid(
                schema, 'Skip GSM/LTE/UMTS towers with an invalid MNC')

        if ((lac_missing or cid_missing) and self.is_missing(data, 'psc')):
            raise Invalid(schema, (
                'Must have (lac and cid) or '
                'psc (psc-only to use in backfill)'))

        if (data['radio'] == Radio.cdma
                and data['cid'] > constants.MAX_CID_CDMA):
            raise Invalid(schema, ('CID is out of range for CDMA.'))

        if (data['radio'] == Radio.lte
                and data['cid'] > constants.MAX_CID_LTE):
            raise Invalid(schema, ('CID is out of range for LTE.'))

        if (data['radio'] in Radio._gsm_family()
                and data['lac'] > constants.MAX_LAC_GSM_UMTS_LTE):
            raise Invalid(schema, ('LAC is out of range for GSM/UMTS/LTE.'))


class ValidCellSchema(ValidCellKeySchema, ValidStationSchema):
    """A schema which validates the fields in cell."""


class ValidOCIDCellSchema(ValidCellSchema):
    """A schema which validates the fields present in a OCID cell."""

    modified = SchemaNode(DateTimeFromString(), missing=None)
    changeable = SchemaNode(Boolean(), missing=True)


class ValidCellLookupSchema(ValidCellKeySchema):
    """A schema which validates the fields in a cell lookup."""

    asu = DefaultNode(Integer(), missing=-1, validator=Range(0, 97))
    signal = DefaultNode(Integer(), missing=0, validator=Range(-150, -1))
    ta = DefaultNode(Integer(), missing=0, validator=Range(0, 63))

    def deserialize(self, data, default_radio=None):
        if data:
            # Sometimes the asu and signal fields are swapped
            if data.get('asu', 0) < -1 and data.get('signal', None) == 0:
                data['signal'] = data['asu']
                data['asu'] = self.fields['asu'].missing
        return super(ValidCellLookupSchema, self).deserialize(
            data, default_radio=default_radio)


class ValidCellReportSchema(ValidCellLookupSchema):
    """A schema which validates the cell specific fields in a report."""


class ValidCellObservationSchema(ValidCellLookupSchema, ValidReportSchema):
    """A schema which validates the fields present in a cell observation."""

    def validator(self, schema, data):
        super(ValidCellObservationSchema, self).validator(schema, data)

        in_country = False
        for code in mobile_codes.mcc(str(data['mcc'])):
            in_country = in_country or geocalc.location_is_in_country(
                data['lat'], data['lon'], code.alpha2, 1)

        if not in_country:
            raise Invalid(schema, (
                'Lat/lon must be inside one of '
                'the bounding boxes for the MCC'))
