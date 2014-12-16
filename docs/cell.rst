.. _cell_records:

============
Cell records
============

As part of the public API, cell records can be sent to identify nearby cells.

Depending on the radio network type, the records contain different information.

The classification of radio types is based on the `Android TelephonyManager
constants <http://developer.android.com/reference/android/telephony/TelephonyManager.html>`_.
A similar classification exists for Firefox OS devices with the
`MozMobileConnectionInfo API <https://developer.mozilla.org/en-US/docs/Web/API/MozMobileConnectionInfo.type>`_.


.. _cell_records_radio_type:

radio
    The type of phone. Must be one of `gsm`, `cdma`, an empty
    string (for example for tablets or laptops without a cell radio)
    or can be omitted entirely.

The top-level radio field identifies the phone type. The radio field in each
cell record specify the type of cell.


GSM
===

If the network is either GSM or any high-data-rate variant of it, the radio
field should be specified as `gsm`. This includes `GSM`, `EDGE` and `GPRS`.

Example:

.. code-block:: javascript

    "radio": "gsm",
    "cell": [
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
    ]

radio **(required)**
    The string `gsm`.

mcc **(required)**
    The mobile country code. An integer in the range of 0 to 999.

mnc **(required)**
    The mobile network code. An integer in the range of 0 to 999.

lac **(required)**
    The location area code. An integer in the range of 1 to 65533.
    According to `TS 24.008 10.5.3 <http://www.etsi.org/deliver/etsi_ts/124000_124099/124008/12.07.00_60/ts_124008v120700p.pdf#page=431>`_ both 0 and 65534 are reserved
    values indicating a deleted state.

cid **(required)**
    The cell id. An integer in the range of 0 to 65535.

signal
    The received signal strength (RSSI) in dBm, typically in the range of
    -51 to -113 (optional).

asu
    The arbitrary strength unit. An integer in the range of 0 to 31 (optional).
    The formula: ``RSSI [dBm] = (2x ASU) – 113``.

ta
    The timing advance. An integer in the range of 0 to 63 (optional).


UMTS
====

If the network is either UMTS or any high-data-rate variant of it, the radio
field should be specified as `umts`. This includes `UMTS`, `HSPA`, `HSDPA`,
`HSPA+` and `HSUPA`.

Example:

.. code-block:: javascript

    "radio": "gsm",
    "cell": [
        {
            "radio": "umts",
            "mcc": 123,
            "mnc": 123,
            "lac": 12345,
            "cid": 123456789,
            "psc": 123,
            "signal": -68,
            "asu": 48
        }
    ]

radio **(required)**
    The string `utms`.

mcc **(required)**
    The mobile country code. An integer in the range of 0 to 999.

mnc **(required)**
    The mobile network code. An integer in the range of 0 to 999.

lac **(required)**
    The location area code. An integer in the range of 1 to 65533.
    According to `TS 24.008 10.5.3 <http://www.etsi.org/deliver/etsi_ts/124000_124099/124008/12.07.00_60/ts_124008v120700p.pdf#page=431>`_ both 0 and 65534 are reserved
    values indicating a deleted state.


cid **(required)**
    The cell id. An integer in the range of 0 to 268435455.

psc
    The primary scrambling code as an integer in the range of 0 to 511
    (optional).

signal
    The received signal code power (RSCP) in dBm, typically in the range of
    -25 to -121 (optional).

asu
    The arbitrary strength unit. An integer in the range of -5 to 91 (optional).
    The formula: ``RSCP [dBm] = ASU - 116``.

A special case exists for UMTS cells, to send data about neighboring cells.
For these it is acceptable to specify the lac and cid fields as `-1` if at
the same time a valid psc field is submitted.

LTE
===

Example:

.. code-block:: javascript

    "radio": "gsm",
    "cell": [
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
    ]

radio **(required)**
    The string `lte`.

mcc **(required)**
    The mobile country code. An integer in the range of 0 to 999.

mnc **(required)**
    The mobile network code. An integer in the range of 0 to 999.

lac **(required)**
    The tracking area code. An integer in the range of 1 to 65533.
    According to `TS 24.301 9.9.3.32 <http://www.etsi.org/deliver/etsi_ts/124300_124399/124301/12.06.00_60/ts_124301v120600p.pdf#page=286>`_ both 0 and 65534 are reserved
    values indicating a deleted state.

cid **(required)**
    The cell identity. An integer in the range of 0 to 268435455.

psc
    The physical cell id as an integer in the range of 0 to 503 (optional).

signal
    The received signal strength (RSRP) in dBm, typically in the range of
    -45 to -137 (optional).

asu
    The arbitrary strength unit. An integer in the range of 0 to 95 (optional).
    The formula: ``RSRP [dBm] = ASU – 140``.

ta
    The timing advance. An integer in the range of 0 to 63 (optional).


A special case exists for LTE cells, to send data about neighboring cells.
For these it is acceptable to specify the lac and cid fields as `-1` if at
the same time a valid psc field is submitted.


CDMA
====

If the network is either CDMA or one of the EVDO variants, the radio
field should be specified as `cdma`. This includes `1xRTT`, `CDMA`, `eHRPD`,
`EVDO_0`, `EVDO_A`, `EVDO_B`, `IS95A` and `IS95B`.

Example:

.. code-block:: javascript

    "radio": "cdma",
    "cell": [
        {
            "radio": "cdma",
            "mcc": 123,
            "mnc": 12345,
            "lac": 12345,
            "cid": 12345,
            "signal": -75,
            "asu": 16
        }
    ]

radio **(required)**
    The string `cdma`. If specified, the phone radio type must also be
    `cdma`.

mcc **(required)**
    The mobile country code. An integer in the range of 0 to 999.

mnc **(required)**
    The system identifier. An integer in the range of 1 to 32767.
    Zero is a reserved value.

lac **(required)**
    The network id. An integer in the range of 1 to 65534.
    Zero is a reserved value indicating base stations not belonging to
    a network. 65535 is a reserved value used in roaming detection.

cid **(required)**
    The base station id. An integer in the range of 0 to 65535.

signal
    The received signal strength (RSSI) in dBm, typically in the range of
    -75 to -100 (optional).

asu
    The arbitrary strength unit. An integer in the range of 1 to 16 (optional).
    Conversion rule: ``RSSI [dBm] >= -75: ASU = 16``,
    ``RSSI [dBm] >= -82: ASU = 8``, ``RSSI [dBm] >= -90: ASU = 4``,
    ``RSSI [dBm] >= -95: ASU = 2``, ``RSSI [dBm] >= -100: ASU = 1``.
