import copy
import datetime
import uuid
from datetime import timedelta

import mobile_codes
from colander import (
    Boolean,
    DateTime,
    Float,
    Integer,
    Invalid,
    MappingSchema,
    Range,
    SchemaNode,
    String,
    iso8601,
)

from ichnaea import geocalc
from ichnaea.customjson import encode_datetime
from ichnaea.data import constants
from ichnaea.models import (
    MAX_RADIO_TYPE,
    MIN_RADIO_TYPE,
    RADIO_TYPE,
)
from ichnaea import util


# Utility functions

def normalized_time(time):
    """
    Takes a string representation of a time value, validates and parses
    it and returns a JSON-friendly string representation of the normalized
    time.

    It rounds down a date to the first of the month.

    It takes any date greater than 60 days into the past
    or in the future and sets it to the current date.
    """
    now = util.utcnow()
    if not time:
        time = None

    try:
        time = iso8601.parse_date(time)
    except (iso8601.ParseError, TypeError):
        time = now
    else:
        # don't accept future time values or
        # time values more than 60 days in the past
        min_time = now - timedelta(days=60)
        if time > now or time < min_time:
            time = now
    # cut down the time to a monthly resolution
    time = time.date().replace(day=1)
    return encode_datetime(time)


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
        if type(cstruct) == datetime.datetime:
            return cstruct
        return super(DateTimeFromString, self).deserialize(schema, cstruct)


class DateTimeToString(String):
    """
    A DateTimeToString will return a string respresentation of a date
    from either a datetime object or a string.
    """

    def deserialize(self, schema, cstruct):
        if type(cstruct) == datetime.datetime:
            cstruct = cstruct.strftime('%Y-%m-%d')
        return super(DateTimeToString, self).deserialize(schema, cstruct)


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


class ReportIDNode(SchemaNode):
    """
    A node containing a valid report_id.
    ex: 489cc8dc9d3d11e4a87d02442b52e5a0
    """

    def preparer(self, cstruct):
        return cstruct or uuid.uuid1().hex


class RoundToMonthDateNode(SchemaNode):
    """
    A node which takes a string date and
    rounds it to the first of the month.
    ex: 2015-01-01
    """

    def preparer(self, cstruct):
        if not cstruct:
            cstruct = datetime.date.today().strftime('%Y-%m-%d')
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


class ValidMeasureSchema(FieldSchema, CopyingSchema):
    """
    A Schema which validates the fields present in a measurement,
    regardless of whether it is a Cell or Wifi measurement.
    """
    lat = SchemaNode(Float(), missing=0.0, validator=Range(
        constants.MIN_LAT, constants.MAX_LAT))
    lon = SchemaNode(Float(), missing=0.0, validator=Range(
        constants.MIN_LON, constants.MAX_LON))
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
    report_id = ReportIDNode(String(), missing='')
    time = RoundToMonthDateNode(DateTimeToString(), missing=None)


class ValidWifiSchema(ValidMeasureSchema):
    """
    A Schema which validates the fields present in a a wifi measurement.
    """
    channel = SchemaNode(Integer(), missing=0, validator=Range(
        constants.MIN_WIFI_CHANNEL, constants.MAX_WIFI_CHANNEL))
    key = WifiKeyNode(String())
    signal = DefaultNode(Integer(), missing=0, validator=Range(
        constants.MIN_WIFI_SIGNAL, constants.MAX_WIFI_SIGNAL))
    signalToNoiseRatio = DefaultNode(
        Integer(), missing=0, validator=Range(0, 100))

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

        return super(ValidWifiSchema, self).deserialize(data)


class ValidCellBaseSchema(ValidMeasureSchema):
    """
    A Schema which validates the fields present in
    all Cell and Cell measurements.
    """
    asu = DefaultNode(Integer(), missing=-1, validator=Range(0, 97))
    cid = DefaultNode(
        Integer(), missing=0, validator=Range(1, constants.MAX_ALL_CID))
    lac = DefaultNode(
        Integer(), missing=0, validator=Range(1, constants.MAX_LAC))
    mcc = SchemaNode(Integer(), validator=Range(1, 999))
    mnc = SchemaNode(Integer(), validator=Range(0, 32767))
    psc = DefaultNode(Integer(), missing=-1, validator=Range(0, 512))
    radio = DefaultNode(
        Integer(), missing=-1, validator=Range(MIN_RADIO_TYPE, MAX_RADIO_TYPE))
    signal = DefaultNode(Integer(), missing=0, validator=Range(-150, -1))
    ta = DefaultNode(Integer(), missing=0, validator=Range(0, 63))

    def deserialize(self, data, default_radio=None):
        if data:
            if 'radio' in data:
                if isinstance(data['radio'], basestring):
                    data['radio'] = RADIO_TYPE.get(
                        data['radio'], self.fields['radio'].missing)

                # If a default radio was set,
                # and we don't know, use it as fallback
                if (self.is_missing(data, 'radio')
                        and default_radio is not None):
                    data['radio'] = default_radio

                # If the cell id >= 65536 then it must be a umts tower
                if (data.get('cid', 0) >= 65536
                        and data['radio'] == RADIO_TYPE['gsm']):
                    data['radio'] = RADIO_TYPE['umts']

            else:
                data['radio'] = default_radio

            # Treat cid=65535 without a valid lac as an unspecified value
            if (self.is_missing(data, 'lac')
                    and data.get('cid', None) == 65535):
                data['cid'] = self.fields['cid'].missing

        return super(ValidCellBaseSchema, self).deserialize(data)

    def validator(self, schema, data):
        lac_missing = self.is_missing(data, 'lac')
        cid_missing = self.is_missing(data, 'cid')

        if data['mcc'] not in constants.ALL_VALID_MCCS:
            raise Invalid(
                schema, 'Check against the list of all known valid mccs')

        if (data['radio'] == RADIO_TYPE['cdma']
                and (lac_missing or cid_missing)):
            raise Invalid(schema, (
                'Skip CDMA towers missing lac or cid '
                '(no psc on CDMA exists to backfill using inference)'))

        radio_types = (
            RADIO_TYPE['gsm'],
            RADIO_TYPE['umts'],
            RADIO_TYPE['lte'],
        )
        if data['radio'] in radio_types and data['mnc'] > 999:
            raise Invalid(
                schema, 'Skip GSM/LTE/UMTS towers with an invalid MNC')

        if ((lac_missing or cid_missing) and self.is_missing(data, 'psc')):
            raise Invalid(schema, (
                'Must have (lac and cid) or '
                'psc (psc-only to use in backfill)'))

        if (data['radio'] == RADIO_TYPE['cdma']
                and data['cid'] > constants.MAX_CDMA_CID):
            raise Invalid(schema, ('CID is out of range for CDMA.'))

        if (data['radio'] == RADIO_TYPE['lte']
                and data['cid'] > constants.MAX_LTE_CID):
            raise Invalid(schema, ('CID is out of range for LTE.'))


class ValidCellSchema(ValidCellBaseSchema):
    """
    A Schema which validates the fields present in
    all Cells.
    """
    created = SchemaNode(DateTimeFromString(), missing=None)
    modified = SchemaNode(DateTimeFromString(), missing=None)
    changeable = SchemaNode(Boolean(), missing=True)
    total_measures = SchemaNode(Integer(), missing=0)
    range = SchemaNode(Integer(), missing=0)


class ValidCellMeasureSchema(ValidCellBaseSchema):
    """
    A Schema which validates the fields present in
    all Cell measurements.
    """
    # pass through created without bothering to validate or decode it again
    created = SchemaNode(String(), missing=None)

    def deserialize(self, data):
        if data:
            # Sometimes the asu and signal fields are swapped
            if data.get('asu', 0) < -1 and data.get('signal', None) == 0:
                data['signal'] = data['asu']
                data['asu'] = self.fields['asu'].missing

        return super(ValidCellMeasureSchema, self).deserialize(data)

    def validator(self, schema, data):
        super(ValidCellMeasureSchema, self).validator(schema, data)

        in_country = False
        for code in mobile_codes.mcc(str(data['mcc'])):
            in_country = in_country or geocalc.location_is_in_country(
                data['lat'], data['lon'], code.alpha2, 1)

        if not in_country:
            raise Invalid(schema, (
                'Lat/lon must be inside one of '
                'the bounding boxes for the MCC'))
