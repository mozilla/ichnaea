import base64

import colander
from sqlalchemy import (
    Column,
    Index,
    PrimaryKeyConstraint,
)
from sqlalchemy.ext.declarative import declared_attr

from ichnaea.models import constants
from ichnaea.models.base import _Model
from ichnaea.models.sa_types import MacColumn
from ichnaea.models.schema import (
    DefaultNode,
    MacNode,
    ValidatorNode,
)
from ichnaea.models.station import (
    StationMixin,
    ValidStationSchema,
)

WIFI_SHARDS = {}


def decode_mac(value, codec=None):
    """
    Decode a 6 byte sequence representing a 48 bit MAC address into a
    hexadecimal, lowercased ASCII string of 12 bytes.

    If ``codec='base64'``, decode the value from a base64 sequence first.
    """
    if codec == 'base64':
        value = base64.b64decode(value)
    return base64.b16encode(value).decode('ascii').lower()


def encode_mac(value, codec=None):
    """
    Given a 12 byte hexadecimal string, return a compact 6 byte
    sequence representing the MAC address.

    If ``codec='base64'``, return the value as a base64 encoded sequence.
    """
    value = base64.b16decode(value.upper())
    if codec == 'base64':
        value = base64.b64encode(value)
    return value


class ValidWifiSignalSchema(colander.MappingSchema, ValidatorNode):
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

            if (channel is None or not
                    (constants.MIN_WIFI_CHANNEL < channel <
                     constants.MAX_WIFI_CHANNEL)):
                # shallow copy
                data = dict(data)
                # if no explicit channel was given, calculate
                freq = data.get('frequency', None)
                if freq is None:
                    freq = 0

                if 2411 < freq < 2473:
                    # 2.4 GHz band
                    data['channel'] = (freq - 2407) // 5

                elif 5169 < freq < 5826:
                    # 5 GHz band
                    data['channel'] = (freq - 5000) // 5

                else:
                    data['channel'] = None

        return super(ValidWifiSignalSchema, self).deserialize(data)


class ValidWifiShardSchema(ValidStationSchema):
    """A schema which validates the fields in a wifi shard."""

    mac = MacNode(colander.String())


class WifiShard(StationMixin):

    _valid_schema = ValidWifiShardSchema()

    mac = Column(MacColumn(6))

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
        global WIFI_SHARDS
        return WIFI_SHARDS.get(cls.shard_id(mac), None)

    @classmethod
    def shards(cls):
        """Return a dict of shard id to model classes."""
        global WIFI_SHARDS
        return WIFI_SHARDS

    @property
    def unique_key(self):
        return self.mac


class WifiShard0(WifiShard, _Model):
    __tablename__ = 'wifi_shard_0'

WIFI_SHARDS['0'] = WifiShard0


class WifiShard1(WifiShard, _Model):
    __tablename__ = 'wifi_shard_1'

WIFI_SHARDS['1'] = WifiShard1


class WifiShard2(WifiShard, _Model):
    __tablename__ = 'wifi_shard_2'

WIFI_SHARDS['2'] = WifiShard2


class WifiShard3(WifiShard, _Model):
    __tablename__ = 'wifi_shard_3'

WIFI_SHARDS['3'] = WifiShard3


class WifiShard4(WifiShard, _Model):
    __tablename__ = 'wifi_shard_4'

WIFI_SHARDS['4'] = WifiShard4


class WifiShard5(WifiShard, _Model):
    __tablename__ = 'wifi_shard_5'

WIFI_SHARDS['5'] = WifiShard5


class WifiShard6(WifiShard, _Model):
    __tablename__ = 'wifi_shard_6'

WIFI_SHARDS['6'] = WifiShard6


class WifiShard7(WifiShard, _Model):
    __tablename__ = 'wifi_shard_7'

WIFI_SHARDS['7'] = WifiShard7


class WifiShard8(WifiShard, _Model):
    __tablename__ = 'wifi_shard_8'

WIFI_SHARDS['8'] = WifiShard8


class WifiShard9(WifiShard, _Model):
    __tablename__ = 'wifi_shard_9'

WIFI_SHARDS['9'] = WifiShard9


class WifiShardA(WifiShard, _Model):
    __tablename__ = 'wifi_shard_a'

WIFI_SHARDS['a'] = WifiShardA


class WifiShardB(WifiShard, _Model):
    __tablename__ = 'wifi_shard_b'

WIFI_SHARDS['b'] = WifiShardB


class WifiShardC(WifiShard, _Model):
    __tablename__ = 'wifi_shard_c'

WIFI_SHARDS['c'] = WifiShardC


class WifiShardD(WifiShard, _Model):
    __tablename__ = 'wifi_shard_d'

WIFI_SHARDS['d'] = WifiShardD


class WifiShardE(WifiShard, _Model):
    __tablename__ = 'wifi_shard_e'

WIFI_SHARDS['e'] = WifiShardE


class WifiShardF(WifiShard, _Model):
    __tablename__ = 'wifi_shard_f'

WIFI_SHARDS['f'] = WifiShardF
