import colander

from ichnaea.models import constants
from ichnaea.models.base import _Model
from ichnaea.models.mac import (
    MacStationMixin,
    ValidMacStationSchema,
)
from ichnaea.models.schema import (
    DefaultNode,
    ValidatorNode,
)

WIFI_SHARDS = {}


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
                elif freq == 2484:
                    data['channel'] = 14
                elif 5169 < freq < 5826:
                    # 5 GHz band
                    data['channel'] = (freq - 5000) // 5
                else:
                    data['channel'] = None

        return super(ValidWifiSignalSchema, self).deserialize(data)


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
