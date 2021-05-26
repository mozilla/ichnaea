"""
Cell Networks
+++++++++++++

As part of the public API and the internal models, we define unique keys
and additional data for each cell network. Depending on the cell radio
network type, these records contain different information.

The classification of radio types is based on the `Android TelephonyManager
constants
<http://developer.android.com/reference/android/telephony/TelephonyManager.html>`_.

GSM
~~~

If the network is either GSM or any high-data-rate variant of it, the radio
type should be specified as `gsm`. This includes `GSM`, `EDGE` and `GPRS`.

Example:

.. code-block:: javascript

    {
        "radio": "gsm",
        "mcc": 123,
        "mnc": 123,
        "lac": 12345,
        "cid": 12345,
        "signal": -61,
        "asu": 26,
        "ta": 10
    }

radio **(required)**
    The string `gsm`.

mcc **(required)**
    The mobile country code. An integer in the range of 1 to 999.

mnc **(required)**
    The mobile network code. An integer in the range of 0 to 999.

lac **(required)**
    The location area code. An integer in the range of 1 to 65533.
    According to `TS 24.008 10.5.3
    <http://www.etsi.org/deliver/etsi_ts/124000_124099/124008/12.07.00_60/ts_124008v120700p.pdf#page=431>`_
    both 0 and 65534 are reserved values indicating a deleted state.

cid **(required)**
    The cell id. An integer in the range of 1 to 65535.

signal
    The received signal strength (RSSI) in dBm, typically in the range of
    -51 to -113 (optional).

asu
    The arbitrary strength unit. An integer in the range of 0 to 31 (optional).
    Unknown values can be marked with a value of 99.
    The formula: ``RSSI [dBm] = (2x ASU) – 113``.

ta
    The timing advance. An integer in the range of 0 to 63 (optional).


WCDMA
~~~~~

If the network is either WCDMA or any high-data-rate variant of it, the radio
field should be specified as `wcdma`. This includes `UMTS`, `HSPA`, `HSDPA`,
`HSPA+` and `HSUPA`.

Example:

.. code-block:: javascript

    {
        "radio": "wcdma",
        "mcc": 123,
        "mnc": 123,
        "lac": 12345,
        "cid": 123456789,
        "psc": 123,
        "signal": -68,
        "asu": 48
    }

radio **(required)**
    The string `wcdma`.

mcc **(required)**
    The mobile country code. An integer in the range of 1 to 999.

mnc **(required)**
    The mobile network code. An integer in the range of 0 to 999.

lac **(required)**
    The location area code. An integer in the range of 1 to 65533.
    According to `TS 24.008 10.5.3
    <http://www.etsi.org/deliver/etsi_ts/124000_124099/124008/12.07.00_60/ts_124008v120700p.pdf#page=431>`_
    both 0 and 65534 are reserved values indicating a deleted state.

cid **(required)**
    The cell id. An integer in the range of 1 to 268435455.

psc
    The primary scrambling code as an integer in the range of 0 to 511
    (optional).

signal
    The received signal code power (RSCP) in dBm, typically in the range of
    -25 to -121 (optional).

asu
    The arbitrary strength unit. An optional integer in the range of -5 to 91.
    Unknown values can be marked with a value of 255.
    The formula: ``RSCP [dBm] = ASU - 116``.

A special case exists for WCDMA cells, to send data about neighboring cells.
For these it is acceptable to omit the lac and cid fields if at the same
time a valid psc field is submitted.


LTE
~~~

Example:

.. code-block:: javascript

    {
        "radio": "lte",
        "mcc": 123,
        "mnc": 123,
        "lac": 12345,
        "cid": 12345,
        "psc": 123,
        "signal": -69,
        "asu": 71,
        "ta": 10
    }

radio **(required)**
    The string `lte`.

mcc **(required)**
    The mobile country code. An integer in the range of 1 to 999.

mnc **(required)**
    The mobile network code. An integer in the range of 0 to 999.

lac **(required)**
    The tracking area code. An integer in the range of 1 to 65533.
    According to `TS 24.301 9.9.3.32
    <http://www.etsi.org/deliver/etsi_ts/124300_124399/124301/12.06.00_60/ts_124301v120600p.pdf#page=286>`_
    both 0 and 65534 are reserved values indicating a deleted state.

cid **(required)**
    The cell identity. An integer in the range of 1 to 268435455.

psc
    The physical cell id as an integer in the range of 0 to 503 (optional).

signal
    The received signal strength (RSRP) in dBm, typically in the range of
    -43 to -140 (optional).

asu
    The arbitrary strength unit. An integer in the range of 0 to 97 (optional).
    The formula: ``RSRP [dBm] = ASU – 140``.

ta
    The timing advance. An integer in the range of 0 to 63 (optional).


A special case exists for LTE cells, to send data about neighboring cells.
For these it is acceptable to omit the lac and cid fields if at the same
time a valid psc field is submitted.


CDMA
~~~~

We classify CDMA networks and their EVDO variants as `cdma`. This includes
`1xRTT`, `CDMA`, `eHRPD`, `EVDO_0`, `EVDO_A`, `EVDO_B`, `IS95A` and `IS95B`.

.. note:: Since CDMA networks are rare and only available in a minority
          of regions, this project does not support them.
"""

import base64
import struct

import colander
from sqlalchemy import (
    BINARY,
    Column,
    Date,
    Index,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import INTEGER as Integer, SMALLINT as SmallInteger
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.types import TypeDecorator

from ichnaea.geocode import GEOCODER
from ichnaea.models.base import _Model, CreationMixin
from ichnaea.models import constants
from ichnaea.models.constants import Radio
from ichnaea.models.sa_types import TinyIntEnum
from ichnaea.models.schema import DateFromString, DefaultNode, ValidatorNode
from ichnaea.models.station import (
    PositionMixin,
    StationMixin,
    TimeTrackingMixin,
    ValidPositionSchema,
    ValidStationSchema,
    ValidTimeTrackingSchema,
)

CELLAREA_STRUCT = struct.Struct("!bHHH")
"""
A compact representation of a full cell area id as a byte sequence.

Consists of a single byte for the radio type and three 16 bit unsigned
integers for the mcc, mnc and lac parts.
"""

CELLID_STRUCT = struct.Struct("!bHHHI")
"""
A compact representation of a full cell id as a byte sequence.

Consists of a single byte for the radio type, three 16 bit unsigned
integers for the mcc, mnc and lac parts and a final 32 bit unsigned
integer for the cid part.
"""

CELL_SHARDS = {}


def decode_cellarea(value, codec=None):
    """
    Decode a byte sequence representing a cell area into a four-tuple
    of a Radio integer enum and three integers.

    If ``codec='base64'``, decode the value from a base64 sequence first.
    """
    if codec == "base64":
        value = base64.b64decode(value)
    radio, mcc, mnc, lac = CELLAREA_STRUCT.unpack(value)
    return (Radio(radio), mcc, mnc, lac)


def decode_cellid(value, codec=None):
    """
    Decode a byte sequence representing a cell id into a five-tuple
    of a Radio integer enum and four integers.

    If ``codec='base64'``, decode the value from a base64 sequence first.
    """
    if codec == "base64":
        value = base64.b64decode(value)
    radio, mcc, mnc, lac, cid = CELLID_STRUCT.unpack(value)
    return (Radio(radio), mcc, mnc, lac, cid)


def encode_cellarea(radio, mcc, mnc, lac, codec=None):
    """
    Given a four-tuple of cell area parts, return a compact 7 byte
    sequence representing the cell area.

    If ``codec='base64'``, return the value as a base64 encoded sequence.
    """
    if isinstance(radio, Radio):
        radio = int(radio)
    value = CELLAREA_STRUCT.pack(radio, mcc, mnc, lac)
    if codec == "base64":
        value = base64.b64encode(value)
    return value


def encode_cellid(radio, mcc, mnc, lac, cid, codec=None):
    """
    Given a five-tuple of cell id parts, return a compact 11 byte
    sequence representing the cell id.

    If ``codec='base64'``, return the value as a base64 encoded sequence.
    """
    if isinstance(radio, Radio):
        radio = int(radio)
    value = CELLID_STRUCT.pack(radio, mcc, mnc, lac, cid)
    if codec == "base64":
        value = base64.b64encode(value)
    return value


def area_id(obj):
    return encode_cellarea(*obj.cellid[:4])


class CellAreaColumn(TypeDecorator):
    """A binary type storing Cell Area IDs."""

    impl = BINARY
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or isinstance(value, bytes):
            return value

        if isinstance(value, tuple) and len(value) != 4:
            raise ValueError("Invalid Cell Area ID: %r" % value)

        radio, mcc, mnc, lac = value
        return CELLAREA_STRUCT.pack(int(radio), mcc, mnc, lac)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        radio, mcc, mnc, lac = CELLAREA_STRUCT.unpack(value)
        return (Radio(radio), mcc, mnc, lac)


class CellIdColumn(TypeDecorator):
    """A binary type storing Cell IDs."""

    impl = BINARY
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or isinstance(value, bytes):
            return value

        if isinstance(value, tuple) and len(value) != 5:
            raise ValueError("Invalid Cell ID: %r" % value)

        radio, mcc, mnc, lac, cid = value
        return CELLID_STRUCT.pack(int(radio), mcc, mnc, lac, cid)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        radio, mcc, mnc, lac, cid = CELLID_STRUCT.unpack(value)
        return (Radio(radio), mcc, mnc, lac, cid)


class RadioType(colander.Integer):
    """A RadioType will return a Radio IntEnum object."""

    def deserialize(self, node, cstruct):
        if (
            isinstance(cstruct, Radio) and cstruct is not Radio["cdma"]
        ) or cstruct is colander.null:
            return cstruct
        error = False
        try:
            cstruct = Radio[cstruct]
            if cstruct is Radio["cdma"]:
                error = True
        except KeyError:
            error = True
        if error:
            raise colander.Invalid(node, ("%r is not a valid radio type" % cstruct))
        return cstruct


class ValidCellAreaKeySchema(colander.MappingSchema, ValidatorNode):

    radio = DefaultNode(RadioType())
    mcc = colander.SchemaNode(colander.Integer())
    mnc = colander.SchemaNode(colander.Integer())
    lac = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(constants.MIN_LAC, constants.MAX_LAC),
    )

    def validator(self, node, cstruct):
        super(ValidCellAreaKeySchema, self).validator(node, cstruct)

        if cstruct["mcc"] not in constants.ALL_VALID_MCCS:
            raise colander.Invalid(
                node, ("Check against the list of all known valid mccs")
            )

        if not (constants.MIN_MNC <= cstruct["mnc"] <= constants.MAX_MNC):
            raise colander.Invalid(node, ("MNC out of valid range."))


class ValidCellKeySchema(ValidCellAreaKeySchema):

    cid = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(constants.MIN_CID, constants.MAX_CID),
    )
    psc = DefaultNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(constants.MIN_PSC, constants.MAX_PSC),
    )

    def __init__(self, *args, **kw):
        super(ValidCellKeySchema, self).__init__(*args, **kw)
        self.radio_node = self.get("radio")

    def deserialize(self, data):
        if data:
            # shallow copy
            data = dict(data)
            # deserialize and validate radio field early
            data["radio"] = self.radio_node.deserialize(
                data.get("radio", colander.null)
            )

            # If the cell id > 65535 then it must be a WCDMA tower
            if (
                data["radio"] is Radio["gsm"]
                and data.get("cid") is not None
                and data.get("cid", 0) > constants.MAX_CID_GSM
            ):
                data["radio"] = Radio["wcdma"]

            if (
                data["radio"] is Radio["lte"]
                and data.get("psc") is not None
                and data.get("psc", 0) > constants.MAX_PSC_LTE
            ):
                data["psc"] = None

        return super(ValidCellKeySchema, self).deserialize(data)

    def validator(self, node, cstruct):
        super(ValidCellKeySchema, self).validator(node, cstruct)

        if (cstruct.get("lac") is None or cstruct.get("cid") is None) and cstruct.get(
            "psc"
        ) is None:
            raise colander.Invalid(node, ("Must have (LAC and CID) or PSC."))


class ValidCellAreaSchema(
    ValidCellAreaKeySchema, ValidPositionSchema, ValidTimeTrackingSchema
):

    # areaid is a derived value
    radius = colander.SchemaNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(0, constants.CELLAREA_MAX_RADIUS),
    )
    region = colander.SchemaNode(colander.String(), missing=None)
    avg_cell_radius = colander.SchemaNode(colander.Integer(), missing=None)
    num_cells = colander.SchemaNode(colander.Integer(), missing=None)
    last_seen = colander.SchemaNode(DateFromString(), missing=None)


class CellAreaMixin(PositionMixin, TimeTrackingMixin, CreationMixin):

    _valid_schema = ValidCellAreaSchema()

    areaid = Column(CellAreaColumn(7))
    radio = Column(TinyIntEnum(Radio), nullable=False)
    mcc = Column(SmallInteger, nullable=False)
    mnc = Column(SmallInteger, nullable=False)
    lac = Column(SmallInteger(unsigned=True), nullable=False)

    radius = Column(Integer)
    region = Column(String(2))
    avg_cell_radius = Column(Integer(unsigned=True))
    num_cells = Column(Integer(unsigned=True))
    last_seen = Column(Date)

    @declared_attr
    def __table_args__(cls):
        prefix = cls.__tablename__
        _indices = (
            PrimaryKeyConstraint("areaid"),
            UniqueConstraint(
                "radio", "mcc", "mnc", "lac", name="%s_areaid_unique" % prefix
            ),
            Index("%s_region_radio_idx" % prefix, "region", "radio"),
            Index("%s_created_idx" % prefix, "created"),
            Index("%s_modified_idx" % prefix, "modified"),
            Index("%s_latlon_idx" % prefix, "lat", "lon"),
        )
        return _indices + (cls._settings,)

    @classmethod
    def validate(cls, entry, _raise_invalid=False, **kw):
        validated = super(CellAreaMixin, cls).validate(
            entry, _raise_invalid=_raise_invalid, **kw
        )
        if validated is not None and "areaid" not in validated:
            validated["areaid"] = (
                validated["radio"],
                validated["mcc"],
                validated["mnc"],
                validated["lac"],
            )

            if (
                ("region" not in validated or not validated["region"])
                and validated["lat"] is not None
                and validated["lon"] is not None
            ):
                validated["region"] = GEOCODER.region_for_cell(
                    validated["lat"], validated["lon"], validated["mcc"]
                )

        return validated


class CellArea(CellAreaMixin, _Model):
    """CellArea model."""

    __tablename__ = "cell_area"


class ValidCellShardSchema(ValidCellKeySchema, ValidStationSchema):

    # adds a range validator
    radius = colander.SchemaNode(
        colander.Integer(),
        missing=None,
        validator=colander.Range(0, constants.CELL_MAX_RADIUS),
    )


class CellShard(StationMixin):
    """Cell shard."""

    _shards = CELL_SHARDS
    _valid_schema = ValidCellShardSchema()

    cellid = Column(CellIdColumn(11))
    radio = Column(TinyIntEnum(Radio), nullable=False)
    mcc = Column(SmallInteger, nullable=False)
    mnc = Column(SmallInteger, nullable=False)
    lac = Column(SmallInteger(unsigned=True), nullable=False)
    cid = Column(Integer(unsigned=True), nullable=False)
    psc = Column(SmallInteger)

    @declared_attr
    def __table_args__(cls):
        _indices = (
            PrimaryKeyConstraint("cellid"),
            UniqueConstraint(
                "radio",
                "mcc",
                "mnc",
                "lac",
                "cid",
                name="%s_cellid_unique" % cls.__tablename__,
            ),
            Index("%s_region_idx" % cls.__tablename__, "region"),
            Index("%s_created_idx" % cls.__tablename__, "created"),
            Index("%s_modified_idx" % cls.__tablename__, "modified"),
            Index("%s_latlon_idx" % cls.__tablename__, "lat", "lon"),
        )
        return _indices + (cls._settings,)

    @property
    def unique_key(self):
        return encode_cellid(*self.cellid)

    @classmethod
    def validate(cls, entry, _raise_invalid=False, **kw):
        validated = super(CellShard, cls).validate(
            entry, _raise_invalid=_raise_invalid, **kw
        )

        if validated is not None:
            if "cellid" not in validated:
                validated["cellid"] = (
                    validated["radio"],
                    validated["mcc"],
                    validated["mnc"],
                    validated["lac"],
                    validated["cid"],
                )

            if (
                ("region" not in validated or not validated["region"])
                and validated["lat"] is not None
                and validated["lon"] is not None
            ):
                validated["region"] = GEOCODER.region_for_cell(
                    validated["lat"], validated["lon"], validated["mcc"]
                )

        return validated

    @classmethod
    def create(cls, _raise_invalid=False, **kw):
        """
        Returns an instance of the correct shard model class, if the
        passed in keyword arguments pass schema validation,
        otherwise returns None.
        """
        validated = cls.validate(kw, _raise_invalid=_raise_invalid)
        if validated is None:
            return None
        shard = cls.shard_model(validated["radio"])
        return shard(**validated)

    @classmethod
    def shard_id(cls, radio):
        """
        Given a radio type return the correct shard id.
        """
        if type(radio) == bytes and len(radio) == 11:
            # extract radio from cellid
            radio = decode_cellid(radio)[0]
        if type(radio) == Radio:
            return radio.name
        if isinstance(radio, tuple) and len(radio) == 5:
            return radio[0].name
        try:
            return Radio[radio].name
        except KeyError:
            pass
        return None

    @classmethod
    def shard_model(cls, radio):
        """
        Given a radio type return the correct DB model class.
        """
        return cls._shards.get(cls.shard_id(radio), None)

    @classmethod
    def shards(cls):
        """Return a dict of shard id to model classes."""
        return cls._shards

    @classmethod
    def export_header(cls):
        return (
            "radio,mcc,mnc,lac,cid,psc,"
            "lat,lon,max_lat,min_lat,max_lon,min_lon,"
            "radius,region,samples,source,weight,"
            "created,modified,last_seen,"
            "block_first,block_last,block_count"
        )

    @classmethod
    def export_stmt(cls):
        stmt = (
            """SELECT
`cellid` AS `export_key`,
CONCAT_WS(",",
    CASE radio
        WHEN 0 THEN "GSM"
        WHEN 2 THEN "WCDMA"
        WHEN 3 THEN "LTE"
        ELSE ""
    END,
    `mcc`,
    `mnc`,
    `lac`,
    `cid`,
    COALESCE(`psc`, ""),
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
WHERE `cellid` > :export_key
ORDER BY `cellid`
LIMIT :limit
"""
            % cls.__tablename__
        )
        return stmt.replace("\n", " ")


class CellShardGsm(CellShard, _Model):
    """Shard for GSM cells."""

    __tablename__ = "cell_gsm"


CELL_SHARDS[Radio.gsm.name] = CellShardGsm


class CellShardWcdma(CellShard, _Model):
    """Shard for WCDMA cells."""

    __tablename__ = "cell_wcdma"


CELL_SHARDS[Radio.wcdma.name] = CellShardWcdma


class CellShardLte(CellShard, _Model):
    """Shard for LTE cells."""

    __tablename__ = "cell_lte"


CELL_SHARDS[Radio.lte.name] = CellShardLte
