import colander
from sqlalchemy import (
    Column,
    Index,
    String,
    UniqueConstraint,
)

from ichnaea.models.base import (
    _Model,
    BigIdMixin,
    CreationMixin,
)
from ichnaea.models import constants
from ichnaea.models.hashkey import (
    HashKey,
    HashKeyMixin,
)
from ichnaea.models.schema import (
    CopyingSchema,
    FieldSchema,
)
from ichnaea.models.station import (
    StationMixin,
    StationBlacklistMixin,
    ValidStationSchema,
)


class WifiKey(HashKey):

    _fields = ('key', )


class WifiKeyMixin(HashKeyMixin):

    _hashkey_cls = WifiKey

    key = Column(String(12))


class WifiKeyNode(colander.SchemaNode):
    """
    A node containing a valid wifi key.
    ex: 01005e901000
    """

    def preparer(self, cstruct):
        # Remove ':' '-' ',' from a wifi key.
        if ":" in cstruct or "-" in cstruct or "." in cstruct:
            cstruct = (cstruct.replace(":", "")
                              .replace("-", "")
                              .replace(".", ""))
        return cstruct.lower()

    def validator(self, node, cstruct):
        valid = constants.INVALID_WIFI_REGEX.match(cstruct) and \
            constants.VALID_WIFI_REGEX.match(cstruct) and len(cstruct) == 12
        if not valid:
            raise colander.Invalid(node, 'Invalid wifi key')


class ValidWifiKeySchema(FieldSchema, CopyingSchema):
    """A schema which validates the fields present in a a wifi key."""

    key = WifiKeyNode(colander.String())


class WifiMixin(BigIdMixin, WifiKeyMixin):
    pass


class ValidWifiSchema(ValidWifiKeySchema, ValidStationSchema):
    """A schema which validates the fields in wifi."""

    new_measures = colander.SchemaNode(colander.Integer(), missing=0)


class Wifi(WifiMixin, StationMixin, CreationMixin, _Model):
    __tablename__ = 'wifi'

    _indices = (
        UniqueConstraint('key', name='wifi_key_unique'),
        Index('wifi_created_idx', 'created'),
        Index('wifi_new_measures_idx', 'new_measures'),
    )
    _valid_schema = ValidWifiSchema

    def __init__(self, *args, **kw):
        if 'new_measures' not in kw:
            kw['new_measures'] = 0
        if 'total_measures' not in kw:
            kw['total_measures'] = 0
        super(Wifi, self).__init__(*args, **kw)


class WifiBlacklist(WifiMixin, StationBlacklistMixin, _Model):
    __tablename__ = 'wifi_blacklist'

    _indices = (
        UniqueConstraint('key', name='wifi_blacklist_key_unique'),
    )
