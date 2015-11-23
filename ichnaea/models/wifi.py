import base64

import colander
from sqlalchemy import (
    Column,
    Date,
    Index,
    String,
    PrimaryKeyConstraint,
)
from sqlalchemy.dialects.mysql import (
    INTEGER as Integer,
    TINYINT as TinyInteger,
)
from sqlalchemy.ext.declarative import declared_attr

from ichnaea.constants import (
    PERMANENT_BLOCKLIST_THRESHOLD,
    TEMPORARY_BLOCKLIST_DURATION,
)
from ichnaea.models import constants
from ichnaea.models.base import (
    _Model,
    CreationMixin,
)
from ichnaea.models.sa_types import (
    MacColumn,
    TinyIntEnum,
)
from ichnaea.models.schema import (
    DateFromString,
    DefaultNode,
    MacNode,
    ValidatorNode,
)
from ichnaea.models.station import (
    BboxMixin,
    PositionMixin,
    ScoreMixin,
    StationSource,
    StationSourceNode,
    StationSourceType,
    TimeTrackingMixin,
    ValidBboxSchema,
    ValidPositionSchema,
    ValidTimeTrackingSchema,
)
from ichnaea import util

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


class ValidWifiShardSchema(ValidBboxSchema,
                           ValidPositionSchema,
                           ValidTimeTrackingSchema):
    """A schema which validates the fields in a wifi shard."""

    mac = MacNode(colander.String())
    radius = colander.SchemaNode(colander.Integer(), missing=0)

    region = colander.SchemaNode(colander.String(), missing=None)
    samples = colander.SchemaNode(colander.Integer(), missing=0)
    source = StationSourceNode(StationSourceType(), missing=None)

    block_first = colander.SchemaNode(DateFromString(), missing=None)
    block_last = colander.SchemaNode(DateFromString(), missing=None)
    block_count = colander.SchemaNode(colander.Integer(), missing=0)


class WifiShard(CreationMixin,
                PositionMixin,
                BboxMixin,
                ScoreMixin,
                TimeTrackingMixin):

    _valid_schema = ValidWifiShardSchema()

    mac = Column(MacColumn(6))

    radius = Column(Integer(unsigned=True))
    region = Column(String(2))
    samples = Column(Integer(unsigned=True))
    source = Column(TinyIntEnum(StationSource))

    block_first = Column(Date)
    block_last = Column(Date)
    block_count = Column(TinyInteger(unsigned=True))

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
        return WIFI_SHARDS.get(mac.lower()[4], None)

    @classmethod
    def shards(cls):
        """Return a dict of shard id to model classes."""
        global WIFI_SHARDS
        return WIFI_SHARDS

    def blocked(self, today=None):
        if (self.block_count and
                self.block_count >= PERMANENT_BLOCKLIST_THRESHOLD):
            return True

        temporary = False
        if self.block_last:
            if today is None:
                today = util.utcnow().date()
            age = today - self.block_last
            temporary = age < TEMPORARY_BLOCKLIST_DURATION

        return bool(temporary)


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
