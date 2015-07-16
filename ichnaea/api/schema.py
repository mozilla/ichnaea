import math
import calendar
import time

import colander
import iso8601


class BoundedFloat(colander.Float):
    """
    A type representing a float, which does not allow
    +/-nan and +/-inf but returns `colander.null` instead.
    """

    def deserialize(self, schema, cstruct):
        value = super(BoundedFloat, self).deserialize(schema, cstruct)
        if value is colander.null or math.isnan(value) or math.isinf(value):
            return colander.null
        return value


class UnixTimeFromInteger(colander.Integer):
    """
    A UnixTimeFromInteger will return an integer representing
    a time value from a unixtime integer or default to now.
    """

    def deserialize(self, schema, cstruct):
        value = super(UnixTimeFromInteger, self).deserialize(schema, cstruct)
        if not value:
            value = time.time() * 1000.0
        return value


class UnixTimeFromString(colander.String):
    """
    A UnixTimeFromString will return an integer representing
    a time value from a ISO datetime string or default to now.
    """

    def deserialize(self, schema, cstruct):
        value = super(UnixTimeFromString, self).deserialize(schema, cstruct)
        timestamp = time.time() * 1000.0
        if value:
            try:
                dt = iso8601.parse_date(value)
                timestamp = calendar.timegm(dt.timetuple()) * 1000.0
            except (iso8601.ParseError, TypeError):  # pragma: no cover
                pass
        return timestamp


class OptionalMapping(colander.Mapping):

    unknown = 'ignore'


class OptionalMappingSchema(colander.Schema):

    schema_type = OptionalMapping


class OptionalSequence(colander.Sequence):
    pass


class OptionalSequenceSchema(colander.Schema):

    schema_type = OptionalSequence


class OptionalNode(colander.SchemaNode):

    missing = colander.drop


class OptionalBoundedFloatNode(OptionalNode):

    schema_type = BoundedFloat


class OptionalIntNode(OptionalNode):

    schema_type = colander.Integer


class OptionalStringNode(OptionalNode):

    schema_type = colander.String


class InternalMixin(object):

    def __init__(self, *args, **kwargs):
        self.internal_name = kwargs.pop('internal_name', None)
        super(InternalMixin, self).__init__(*args, **kwargs)


class InternalSchemaNode(InternalMixin, colander.SchemaNode):
    pass


class InternalMapping(colander.Mapping):

    def _impl(self, node, *args, **kwargs):
        result = super(InternalMapping, self)._impl(node, *args, **kwargs)
        internal_result = {}
        for subnode in node.children:
            subnode_internal_name = getattr(
                subnode, 'internal_name', subnode.name) or subnode.name

            if result[subnode.name]:
                internal_result[subnode_internal_name] = result[subnode.name]

        return internal_result
