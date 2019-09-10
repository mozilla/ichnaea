from base64 import b16decode, b16encode, b64decode, b64encode

import colander
from sqlalchemy import BINARY, Column, Index, PrimaryKeyConstraint
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.types import TypeDecorator

from ichnaea.models.constants import INVALID_MAC_REGEX, VALID_MAC_REGEX
from ichnaea.models.schema import ValidatorNode
from ichnaea.models.station import StationMixin, ValidStationSchema


def channel_frequency(channel, frequency):
    """
    Takes a WiFi channel and frequency value and if one of them is None,
    derives it from the other.
    """
    new_channel = channel
    new_frequency = frequency
    if frequency is None and channel is not None:
        if 0 < channel < 14:
            # 2.4 GHz band
            new_frequency = (channel * 5) + 2407
        elif channel == 14:
            new_frequency = 2484
        elif 14 < channel < 186:
            # 5 GHz band, incl. UNII4
            new_frequency = (channel * 5) + 5000
        elif 185 < channel < 200:
            # 4.9 GHz band
            new_frequency = (channel * 5) + 4000
    elif frequency is not None and channel is None:
        if 2411 < frequency < 2473:
            # 2.4 GHz band
            new_channel = (frequency - 2407) // 5
        elif frequency == 2484:
            new_channel = 14
        elif 4914 < frequency < 4996:
            # 4.9 GHz band
            new_channel = (frequency - 4000) // 5
        elif 5074 < frequency < 5926:
            # 5 GHz band, incl. UNII4
            new_channel = (frequency - 5000) // 5

    return (new_channel, new_frequency)


def decode_mac(value, codec=None):
    """
    Decode a 6 byte sequence representing a 48 bit MAC address into a
    hexadecimal, lowercased ASCII string of 12 bytes.

    If ``codec='base64'``, decode the value from a base64 sequence first.
    """
    if codec == "base64":
        value = b64decode(value)
    return b16encode(value).decode("ascii").lower()


def encode_mac(value, codec=None):
    """
    Given a 12 byte hexadecimal string, return a compact 6 byte
    sequence representing the MAC address.

    If ``codec='base64'``, return the value as a base64 encoded sequence.
    """
    value = b16decode(value.upper())
    if codec == "base64":
        value = b64encode(value)
    return value


class MacColumn(TypeDecorator):
    """A binary type storing MAC's."""

    impl = BINARY

    def process_bind_param(self, value, dialect):
        if value and len(value) == 6:
            return value
        if not (value and len(value) == 12):
            raise ValueError("Invalid MAC: %r" % value)
        return b16decode(value.upper().encode("ascii"))

    def process_result_value(self, value, dialect):
        if value is None:  # pragma: no cover
            return value
        return b16encode(value).decode("ascii").lower()


class MacNode(ValidatorNode):
    """A node containing a valid mac address, ex: 01005e901000.
    """

    def preparer(self, cstruct):
        # Remove ':' '-' ',' from a wifi BSSID
        if cstruct and (":" in cstruct or "-" in cstruct or "." in cstruct):
            cstruct = cstruct.replace(":", "").replace("-", "").replace(".", "")
        return cstruct and cstruct.lower() or colander.null

    def validator(self, node, cstruct):
        super(MacNode, self).validator(node, cstruct)

        valid = (
            len(cstruct) == 12
            and INVALID_MAC_REGEX.match(cstruct)
            and VALID_MAC_REGEX.match(cstruct)
        )

        if not valid:
            raise colander.Invalid(node, "Invalid mac address.")


class ValidMacStationSchema(ValidStationSchema):
    """A schema which validates the fields in a mac address based shard."""

    mac = MacNode(colander.String())


class MacStationMixin(StationMixin):
    """
    A mixin class for station whose primary key is a mac address.
    """

    _shards = None

    mac = Column(MacColumn(6))

    @declared_attr
    def __table_args__(cls):  # NOQA
        _indices = (
            PrimaryKeyConstraint("mac"),
            Index("%s_region_idx" % cls.__tablename__, "region"),
            Index("%s_created_idx" % cls.__tablename__, "created"),
            Index("%s_modified_idx" % cls.__tablename__, "modified"),
            Index("%s_latlon_idx" % cls.__tablename__, "lat", "lon"),
        )
        return _indices + (cls._settings,)

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
        shard = cls.shard_model(validated["mac"])
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

    @classmethod
    def export_header(cls):
        return (
            "mac,"
            "lat,lon,max_lat,min_lat,max_lon,min_lon,"
            "radius,region,samples,source,weight,"
            "created,modified,last_seen,"
            "block_first,block_last,block_count"
        )

    @classmethod
    def export_stmt(cls):
        stmt = (
            """SELECT
`mac` AS `export_key`,
CONCAT_WS(",",
    LOWER(HEX(`mac`)),
    COALESCE(ROUND(`lat`, 7), ""),
    COALESCE(ROUND(`lon`, 7), ""),
    COALESCE(ROUND(`max_lat`, 7), ""),
    COALESCE(ROUND(`min_lat`, 7), ""),
    COALESCE(ROUND(`max_lon`, 7), ""),
    COALESCE(ROUND(`min_lon`, 7), ""),
    COALESCE(`radius`, "0"),
    COALESCE(`region`, ""),
    COALESCE(`samples`, "0"),
    COALESCE(`source`, ""),
    COALESCE(`weight`, "0"),
    COALESCE(UNIX_TIMESTAMP(`created`), ""),
    COALESCE(UNIX_TIMESTAMP(`modified`), ""),
    COALESCE(UNIX_TIMESTAMP(`last_seen`), ""),
    COALESCE(UNIX_TIMESTAMP(`block_first`), ""),
    COALESCE(UNIX_TIMESTAMP(`block_last`), ""),
    COALESCE(`block_count`, "0")
) AS `export_value`
FROM %s
WHERE `mac` > :export_key
ORDER BY `mac`
LIMIT :limit
"""
            % cls.__tablename__
        )
        return stmt.replace("\n", " ")
