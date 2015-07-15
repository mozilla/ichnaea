import copy
from datetime import datetime

import colander


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
            if self.missing is colander.required:
                raise
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
