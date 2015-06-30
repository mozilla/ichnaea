import colander
from sqlalchemy import (
    Column,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import (
    SMALLINT as SmallInteger,
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
    DefaultNode,
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
    _query_batch = 100

    key = Column(String(12))


class WifiKeyNode(colander.SchemaNode):
    """
    A node containing a valid wifi key.
    ex: 01005e901000
    """

    def preparer(self, cstruct):
        # Remove ':' '-' ',' from a wifi key.
        if cstruct and (':' in cstruct or '-' in cstruct or '.' in cstruct):
            cstruct = (cstruct.replace(':', '')
                              .replace('-', '')
                              .replace('.', ''))
        return cstruct and cstruct.lower() or colander.null

    def validator(self, node, cstruct):
        valid = (len(cstruct) == 12 and
                 constants.INVALID_WIFI_REGEX.match(cstruct) and
                 constants.VALID_WIFI_REGEX.match(cstruct))
        if not valid:
            raise colander.Invalid(node, 'Invalid wifi key')


class ValidWifiKeySchema(FieldSchema, CopyingSchema):
    """A schema which validates the fields present in a a wifi key."""

    key = WifiKeyNode(colander.String())


class WifiSignalMixin(object):

    channel = Column(SmallInteger)
    signal = Column(SmallInteger)
    snr = Column(SmallInteger)


class ValidWifiSignalSchema(FieldSchema, CopyingSchema):
    """
    A schema which validates the fields related to wifi signal
    strength and quality.
    """

    channel = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(
            constants.MIN_WIFI_CHANNEL, constants.MAX_WIFI_CHANNEL))
    signal = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(
            constants.MIN_WIFI_SIGNAL, constants.MAX_WIFI_SIGNAL))
    snr = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(0, 100))

    def deserialize(self, data):
        if data:
            channel = data.get('channel')
            channel = channel is not None and int(channel) or None

            if not (constants.MIN_WIFI_CHANNEL < channel <
                    constants.MAX_WIFI_CHANNEL):
                # if no explicit channel was given, calculate
                freq = data.get('frequency', 0)

                if 2411 < freq < 2473:
                    # 2.4 GHz band
                    data['channel'] = (freq - 2407) // 5

                elif 5169 < freq < 5826:
                    # 5 GHz band
                    data['channel'] = (freq - 5000) // 5

                else:
                    data['channel'] = None

        return super(ValidWifiSignalSchema, self).deserialize(data)


class WifiMixin(BigIdMixin, WifiKeyMixin):
    pass


class ValidWifiSchema(ValidWifiKeySchema, ValidStationSchema):
    """A schema which validates the fields in wifi."""


class Wifi(WifiMixin, StationMixin, CreationMixin, _Model):
    __tablename__ = 'wifi'

    _indices = (
        UniqueConstraint('key', name='wifi_key_unique'),
        Index('wifi_created_idx', 'created'),
    )
    _valid_schema = ValidWifiSchema


class WifiBlacklist(WifiMixin, StationBlacklistMixin, _Model):
    __tablename__ = 'wifi_blacklist'

    _indices = (
        UniqueConstraint('key', name='wifi_blacklist_key_unique'),
    )
