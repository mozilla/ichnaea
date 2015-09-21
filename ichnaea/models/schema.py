from datetime import date, datetime

import colander

from ichnaea.models.constants import (
    INVALID_MAC_REGEX,
    VALID_MAC_REGEX,
)


class DateFromString(colander.Date):
    """
    A DateFromString will return a date object
    from either a date object or a string.
    """

    def deserialize(self, schema, cstruct):
        if type(cstruct) == date:
            return cstruct
        return super(DateFromString, self).deserialize(
            schema, cstruct)  # pragma: no cover


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


class MacNode(ValidatorNode):
    """A node containing a valid mac address, ex: 01005e901000.
    """

    def preparer(self, cstruct):
        # Remove ':' '-' ',' from a wifi BSSID
        if cstruct and (':' in cstruct or '-' in cstruct or '.' in cstruct):
            cstruct = (cstruct.replace(':', '')
                              .replace('-', '')
                              .replace('.', ''))
        return cstruct and cstruct.lower() or colander.null

    def validator(self, node, cstruct):
        super(MacNode, self).validator(node, cstruct)

        valid = (len(cstruct) == 12 and
                 INVALID_MAC_REGEX.match(cstruct) and
                 VALID_MAC_REGEX.match(cstruct))

        if not valid:
            raise colander.Invalid(node, 'Invalid mac address.')
