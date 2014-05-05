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
    The radio type. Must be one of "gsm", "cdma" or an empty
    string (for example for tablets or laptops without a cell radio).

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

mcc
    The mobile country code. An integer in the range of 0 to 999 (required).

mnc
    The mobile network code. An integer in the range of 0 to 999 (required).

lac
    The location area code. An integer in the range of 0 to 65535 (optional).

cid
    The cell id. An integer in the range of 0 to 65535 (required).

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

mcc
    The mobile country code. An integer in the range of 0 to 999 (required).

mnc
    The mobile network code. An integer in the range of 0 to 999 (required).

lac
    The location area code. An integer in the range of 0 to 65535 (optional).

cid
    The cell id. An integer in the range of 0 to 268435455 (optional).

psc
    The primary scrambling code as an integer in the range of 0 to 511
    (optional).

signal
    The received signal code power (RSCP) in dBm, typically in the range of
    -25 to -121 (optional).

asu
    The arbitrary strength unit. An integer in the range of -5 to 91 (optional).
    The formula: ``RSCP [dBm] = ASU - 116``.


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

mcc
    The mobile country code. An integer in the range of 0 to 999 (required).

mnc
    The system identifier. An integer in the range of 0 to 32767 (required).

lac
    The network id. An integer in the range of 0 to 65535 (required).

cid
    The base station id. An integer in the range of 0 to 65535 (required).

signal
    The received signal strength (RSSI) in dBm, typically in the range of
    -75 to -100 (optional).

asu
    The arbitrary strength unit. An integer in the range of 1 to 16 (optional).
    Conversion rule: ``RSSI [dBm] >= -75: ASU = 16``,
    ``RSSI [dBm] >= -82: ASU = 8``, ``RSSI [dBm] >= -90: ASU = 4``,
    ``RSSI [dBm] >= -95: ASU = 2``, ``RSSI [dBm] >= -100: ASU = 1``.


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

mcc
    The mobile country code. An integer in the range of 0 to 999 (required).

mnc
    The mobile network code. An integer in the range of 0 to 999 (required).

lac
    The tracking area code. An integer in the range of 0 to 65535 (optional).

cid
    The cell identity. An integer in the range of 0 to 268435455 (required).

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
