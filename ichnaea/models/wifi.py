from ichnaea.models.base import _Model
from ichnaea.models.mac import (
    MacStationMixin,
    ValidMacStationSchema,
)

WIFI_SHARDS = {}


class ValidWifiShardSchema(ValidMacStationSchema):
    """A schema which validates the fields in a WiFi shard."""


class WifiShard(MacStationMixin):
    """WiFi shard."""

    _shards = WIFI_SHARDS
    _valid_schema = ValidWifiShardSchema()


class WifiShard0(WifiShard, _Model):
    """WiFi shard 0."""
    __tablename__ = 'wifi_shard_0'

WIFI_SHARDS['0'] = WifiShard0


class WifiShard1(WifiShard, _Model):
    """WiFi shard 1."""
    __tablename__ = 'wifi_shard_1'

WIFI_SHARDS['1'] = WifiShard1


class WifiShard2(WifiShard, _Model):
    """WiFi shard 2."""
    __tablename__ = 'wifi_shard_2'

WIFI_SHARDS['2'] = WifiShard2


class WifiShard3(WifiShard, _Model):
    """WiFi shard 3."""
    __tablename__ = 'wifi_shard_3'

WIFI_SHARDS['3'] = WifiShard3


class WifiShard4(WifiShard, _Model):
    """WiFi shard 4."""
    __tablename__ = 'wifi_shard_4'

WIFI_SHARDS['4'] = WifiShard4


class WifiShard5(WifiShard, _Model):
    """WiFi shard 5."""
    __tablename__ = 'wifi_shard_5'

WIFI_SHARDS['5'] = WifiShard5


class WifiShard6(WifiShard, _Model):
    """WiFi shard 6."""
    __tablename__ = 'wifi_shard_6'

WIFI_SHARDS['6'] = WifiShard6


class WifiShard7(WifiShard, _Model):
    """WiFi shard 7."""
    __tablename__ = 'wifi_shard_7'

WIFI_SHARDS['7'] = WifiShard7


class WifiShard8(WifiShard, _Model):
    """WiFi shard 8."""
    __tablename__ = 'wifi_shard_8'

WIFI_SHARDS['8'] = WifiShard8


class WifiShard9(WifiShard, _Model):
    """WiFi shard 9."""
    __tablename__ = 'wifi_shard_9'

WIFI_SHARDS['9'] = WifiShard9


class WifiShardA(WifiShard, _Model):
    """WiFi shard A."""
    __tablename__ = 'wifi_shard_a'

WIFI_SHARDS['a'] = WifiShardA


class WifiShardB(WifiShard, _Model):
    """WiFi shard B."""
    __tablename__ = 'wifi_shard_b'

WIFI_SHARDS['b'] = WifiShardB


class WifiShardC(WifiShard, _Model):
    """WiFi shard C."""
    __tablename__ = 'wifi_shard_c'

WIFI_SHARDS['c'] = WifiShardC


class WifiShardD(WifiShard, _Model):
    """WiFi shard D."""
    __tablename__ = 'wifi_shard_d'

WIFI_SHARDS['d'] = WifiShardD


class WifiShardE(WifiShard, _Model):
    """WiFi shard E."""
    __tablename__ = 'wifi_shard_e'

WIFI_SHARDS['e'] = WifiShardE


class WifiShardF(WifiShard, _Model):
    """WiFi shard F."""
    __tablename__ = 'wifi_shard_f'

WIFI_SHARDS['f'] = WifiShardF
