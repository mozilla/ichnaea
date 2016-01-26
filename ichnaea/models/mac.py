from base64 import (
    b16decode,
    b16encode,
    b64decode,
    b64encode
)

import colander
from sqlalchemy import (
    BINARY,
    Column,
    Index,
    PrimaryKeyConstraint,
)
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.types import TypeDecorator

from ichnaea.models.constants import (
    INVALID_MAC_REGEX,
    VALID_MAC_REGEX,
)
from ichnaea.models.schema import ValidatorNode
from ichnaea.models.station import (
    StationMixin,
    ValidStationSchema,
)


def decode_mac(value, codec=None):
    """
    Decode a 6 byte sequence representing a 48 bit MAC address into a
    hexadecimal, lowercased ASCII string of 12 bytes.

    If ``codec='base64'``, decode the value from a base64 sequence first.
    """
    if codec == 'base64':
        value = b64decode(value)
    return b16encode(value).decode('ascii').lower()


def encode_mac(value, codec=None):
    """
    Given a 12 byte hexadecimal string, return a compact 6 byte
    sequence representing the MAC address.

    If ``codec='base64'``, return the value as a base64 encoded sequence.
    """
    value = b16decode(value.upper())
    if codec == 'base64':
        value = b64encode(value)
    return value


class MacColumn(TypeDecorator):
    """A binary type storing MAC's."""

    impl = BINARY

    def process_bind_param(self, value, dialect):
        if not (value and len(value) == 12):
            raise ValueError('Invalid MAC: %r' % value)
        return b16decode(value.upper().encode('ascii'))

    def process_result_value(self, value, dialect):
        if value is None:  # pragma: no cover
            return value
        return b16encode(value).decode('ascii').lower()


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


class ValidMacStationSchema(ValidStationSchema):
    """A schema which validates the fields in a mac address based shard."""

    mac = MacNode(colander.String())


class MacStationMixin(StationMixin):
    """
    A mixin class for station whose primary key is a mac address.
    """

    _shards = None

    mac = Column(MacColumn(6))  #:

    @declared_attr
    def __table_args__(cls):  # NOQA
        _indices = (
            PrimaryKeyConstraint('mac'),
            Index('%s_region_idx' % cls.__tablename__, 'region'),
            Index('%s_created_idx' % cls.__tablename__, 'created'),
            Index('%s_modified_idx' % cls.__tablename__, 'modified'),
            Index('%s_latlon_idx' % cls.__tablename__, 'lat', 'lon'),
        )
        return _indices + (cls._settings, )

    @classmethod
    def create(cls, _raise_invalid=False, **kw):
        """
        Returns an instance of the correct shard model class, if the
        passed in keyword arguments pass schema validation,
        otherwise returns None.
        """
        validated = cls.validate(kw, _raise_invalid=_raise_invalid)
        if validated is None:  # pragma: no cover
            return None
        shard = cls.shard_model(validated['mac'])
        return shard(**validated)

    @classmethod
    def shard_id(cls, mac):
        """
        Given a BSSID/MAC return the correct shard id for this data.
        """
        if not mac:
            return None
        if type(mac) == bytes and len(mac) == 6:
            # mac is encoded as bytes
            mac = decode_mac(mac)
        return mac.lower()[4]

    @classmethod
    def shard_model(cls, mac):
        """
        Given a BSSID/MAC return the correct DB model class for this
        shard of data.

        The shard id is based on the fifth hex character of the vendor
        prefix of the BSSID. This tends to be evenly distributed, but
        still keeps data from the same vendor inside the same table.

        It also allows us to later extend the sharding by taking in
        parts of the sixth hex char without having to do a complete
        re-sharding of everything, but merely breaking up each shard
        further.
        """
        if not mac:
            return None
        return cls._shards.get(cls.shard_id(mac), None)

    @classmethod
    def shards(cls):
        """Return a dict of shard id to model classes."""
        return cls._shards

    @property
    def unique_key(self):
        return self.mac
