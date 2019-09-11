from datetime import date, datetime

import colander

from ichnaea.models.constants import ReportSource


class DateFromString(colander.Date):
    """
    A DateFromString will return a date object
    from either a date object or a string.
    """

    def deserialize(self, schema, cstruct):
        if type(cstruct) == date:
            return cstruct
        return super(DateFromString, self).deserialize(schema, cstruct)


class DateTimeFromString(colander.DateTime):
    """
    A DateTimeFromString will return a datetime object
    from either a datetime object or a string.
    """

    def deserialize(self, schema, cstruct):
        if type(cstruct) == datetime:
            return cstruct
        return super(DateTimeFromString, self).deserialize(schema, cstruct)


class ValidatorNode(colander.SchemaNode):
    """
    A ValidatorNode is a schema node which defines validator as a callable
    method, so all subclasses can rely on calling it via super().
    """

    def validator(self, node, cstruct):
        pass


class DefaultNode(ValidatorNode):
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


class ReportSourceNode(DefaultNode):
    """A node containing a valid report source."""

    def validator(self, node, cstruct):
        super(ReportSourceNode, self).validator(node, cstruct)

        if type(cstruct) is ReportSource:
            return True

        raise colander.Invalid(node, "Invalid station source")


class ReportSourceType(colander.Integer):
    """
    A ReportSourceType will return a ReportSource IntEnum object.
    """

    def deserialize(self, node, cstruct):
        if cstruct is colander.null:
            return None
        if isinstance(cstruct, ReportSource):
            return cstruct
        try:
            if isinstance(cstruct, str):
                cstruct = ReportSource[cstruct]
            else:
                cstruct = ReportSource(cstruct)
        except (KeyError, ValueError):
            raise colander.Invalid(node, ("%r is not a valid station source" % cstruct))
        return cstruct
