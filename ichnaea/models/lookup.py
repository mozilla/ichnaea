import colander
from sqlalchemy import Column
from sqlalchemy.dialects.mysql import (
    SMALLINT as SmallInteger,
    TINYINT as TinyInteger,
)

from ichnaea.models.base import ValidationMixin
from ichnaea.models.cell import (
    CellKey,
    CellKeyPscMixin,
    ValidCellAreaKeySchema,
    ValidCellKeySchema,
)
from ichnaea.models import constants
from ichnaea.models.schema import DefaultNode
from ichnaea.models.wifi import (
    ValidWifiKeySchema,
    WifiKeyMixin,
)


class CellAreaLookup(CellKeyPscMixin, ValidationMixin):

    _hashkey_cls = CellKey
    _valid_schema = ValidCellAreaKeySchema

    asu = Column(SmallInteger)
    signal = Column(SmallInteger)
    ta = Column(TinyInteger)


class ValidCellLookupSchema(ValidCellKeySchema):
    """A schema which validates the fields in a cell lookup."""

    asu = DefaultNode(
        colander.Integer(),
        missing=None, validator=colander.Range(0, 97))
    signal = DefaultNode(
        colander.Integer(),
        missing=None, validator=colander.Range(-150, -1))
    ta = DefaultNode(
        colander.Integer(),
        missing=None, validator=colander.Range(0, 63))

    def deserialize(self, data):
        if data:
            # Sometimes the asu and signal fields are swapped
            if data.get('asu', 0) < -1 and data.get('signal', None) == 0:
                data['signal'] = data['asu']
                data['asu'] = None
        return super(ValidCellLookupSchema, self).deserialize(data)


class CellLookup(CellAreaLookup):

    _valid_schema = ValidCellLookupSchema


class ValidWifiLookupSchema(ValidWifiKeySchema):
    """A schema which validates the fields in a wifi lookup."""

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

        return super(ValidWifiLookupSchema, self).deserialize(data)


class WifiLookup(WifiKeyMixin, ValidationMixin):

    _valid_schema = ValidWifiLookupSchema
