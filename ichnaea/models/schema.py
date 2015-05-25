import copy
from datetime import date, datetime, timedelta

import colander
import iso8601
from pytz import UTC

from ichnaea import util


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
    elif isinstance(time, (str, unicode)):
        try:
            time = iso8601.parse_date(time)
        except (iso8601.ParseError, TypeError):
            time = now
    elif type(time) == date:
        time = datetime(time.year, time.month, time.day, tzinfo=UTC)

    # don't accept future time values or
    # time values more than 60 days in the past
    min_time = now - timedelta(days=60)
    if time > now or time < min_time:
        time = now

    # cut down the time to a monthly resolution
    time = time.replace(day=1, hour=0, minute=0, second=0,
                        microsecond=0, tzinfo=UTC)
    return time


class DateTimeFromString(colander.DateTime):
    """
    A DateTimeFromString will return a datetime object
    from either a datetime object or a string.
    """

    def deserialize(self, schema, cstruct):
        if type(cstruct) == datetime:
            return cstruct
        return super(DateTimeFromString, self).deserialize(schema, cstruct)


class DefaultNode(colander.SchemaNode):
    """
    A DefaultNode will use its ``missing`` value
    if it fails to validate during deserialization.
    """

    def deserialize(self, cstruct):
        try:
            return super(DefaultNode, self).deserialize(cstruct)
        except colander.Invalid:
            return self.missing


class CopyingSchema(colander.MappingSchema):
    """
    A Schema which makes a copy of the passed in dict to validate.
    """

    def deserialize(self, data):
        return super(CopyingSchema, self).deserialize(copy.copy(data))


class FieldSchema(colander.MappingSchema):
    """
    A schema which provides an interface to its fields through the
    .fields[field_name] interface.
    """

    @property
    def fields(self):
        return dict([(field.name, field) for field in self.children])
