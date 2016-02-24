"""
This module contains basic colander types used in the public locate and
submit HTTP APIs.

The Optional* classes are used primarily in the submit APIs and drop any
non-valid or not-found fields. This results in the smallest possible JSON
representation to be send over the network to the backend queue.

The locate APIs prefer to deserialize data into a consistent in-memory
representation with all fields being present and missing values of
`None` or empty tuples.
"""

import calendar
import math
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
        if (value is colander.null or (
                isinstance(value, float) and
                (math.isnan(value) or math.isinf(value)))):
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


class RenamingMapping(colander.Mapping):
    """
    A RenamingMapping is a colander mapping that supports an additional
    `to_name` argument. During deserialization the keys in the input
    dictionary aren't left untouched, but instead mapped from their
    original value to the `to_name` field.

    The opposite support of taking a value from a different field isn't
    implemented.
    """

    def _impl(self, node, *args, **kw):
        result = super(RenamingMapping, self)._impl(node, *args, **kw)
        renamed_result = {}
        for subnode in node.children:
            subnode_to_name = getattr(
                subnode, 'to_name', subnode.name) or subnode.name

            subnode_value = result.get(subnode.name, subnode.missing)
            if (subnode_value is colander.drop or
                    subnode_value is colander.null):  # pragma: no cover
                continue
            else:
                renamed_result[subnode_to_name] = subnode_value

        return renamed_result


class RenamingMappingSchema(colander.MappingSchema):

    schema_type = RenamingMapping  #:


class OptionalMapping(RenamingMapping):

    unknown = 'ignore'  #:


class OptionalMappingSchema(RenamingMappingSchema):

    schema_type = OptionalMapping  #:


class OptionalSequence(colander.Sequence):

    missing = colander.drop  #:


class OptionalSequenceSchema(colander.SequenceSchema):

    schema_type = OptionalSequence  #:


class OptionalNode(colander.SchemaNode):

    missing = colander.drop  #:


class OptionalBoundedFloatNode(OptionalNode):

    schema_type = BoundedFloat  #:


class OptionalIntNode(OptionalNode):

    schema_type = colander.Integer  #:


class OptionalStringNode(OptionalNode):

    schema_type = colander.String  #:
