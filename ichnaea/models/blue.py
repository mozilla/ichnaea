from ichnaea.models.base import _Model
from ichnaea.models.mac import (
    MacStationMixin,
    ValidMacStationSchema,
)

BLUE_SHARDS = {}


class ValidBlueShardSchema(ValidMacStationSchema):
    """A schema which validates the fields in a Bluetooth shard."""


class BlueShard(MacStationMixin):
    """Bluetooth shard."""

    _shards = BLUE_SHARDS
    _valid_schema = ValidBlueShardSchema()


class BlueShard0(BlueShard, _Model):
    """Bluetooth shard 0."""
    __tablename__ = 'blue_shard_0'

BLUE_SHARDS['0'] = BlueShard0


class BlueShard1(BlueShard, _Model):
    """Bluetooth shard 1."""
    __tablename__ = 'blue_shard_1'

BLUE_SHARDS['1'] = BlueShard1


class BlueShard2(BlueShard, _Model):
    """Bluetooth shard 2."""
    __tablename__ = 'blue_shard_2'

BLUE_SHARDS['2'] = BlueShard2


class BlueShard3(BlueShard, _Model):
    """Bluetooth shard 3."""
    __tablename__ = 'blue_shard_3'

BLUE_SHARDS['3'] = BlueShard3


class BlueShard4(BlueShard, _Model):
    """Bluetooth shard 4."""
    __tablename__ = 'blue_shard_4'

BLUE_SHARDS['4'] = BlueShard4


class BlueShard5(BlueShard, _Model):
    """Bluetooth shard 5."""
    __tablename__ = 'blue_shard_5'

BLUE_SHARDS['5'] = BlueShard5


class BlueShard6(BlueShard, _Model):
    """Bluetooth shard 6."""
    __tablename__ = 'blue_shard_6'

BLUE_SHARDS['6'] = BlueShard6


class BlueShard7(BlueShard, _Model):
    """Bluetooth shard 7."""
    __tablename__ = 'blue_shard_7'

BLUE_SHARDS['7'] = BlueShard7


class BlueShard8(BlueShard, _Model):
    """Bluetooth shard 8."""
    __tablename__ = 'blue_shard_8'

BLUE_SHARDS['8'] = BlueShard8


class BlueShard9(BlueShard, _Model):
    """Bluetooth shard 9."""
    __tablename__ = 'blue_shard_9'

BLUE_SHARDS['9'] = BlueShard9


class BlueShardA(BlueShard, _Model):
    """Bluetooth shard A."""
    __tablename__ = 'blue_shard_a'

BLUE_SHARDS['a'] = BlueShardA


class BlueShardB(BlueShard, _Model):
    """Bluetooth shard B."""
    __tablename__ = 'blue_shard_b'

BLUE_SHARDS['b'] = BlueShardB


class BlueShardC(BlueShard, _Model):
    """Bluetooth shard C."""
    __tablename__ = 'blue_shard_c'

BLUE_SHARDS['c'] = BlueShardC


class BlueShardD(BlueShard, _Model):
    """Bluetooth shard D."""
    __tablename__ = 'blue_shard_d'

BLUE_SHARDS['d'] = BlueShardD


class BlueShardE(BlueShard, _Model):
    """Bluetooth shard E."""
    __tablename__ = 'blue_shard_e'

BLUE_SHARDS['e'] = BlueShardE


class BlueShardF(BlueShard, _Model):
    """Bluetooth shard F."""
    __tablename__ = 'blue_shard_f'

BLUE_SHARDS['f'] = BlueShardF
