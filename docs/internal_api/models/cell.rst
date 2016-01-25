:mod:`ichnaea.models.cell`
--------------------------

.. automodule:: ichnaea.models.cell
    :members:
    :member-order: bysource

Cell Networks
+++++++++++++

As part of the public API and the internal models, we define unique keys
and additional data for each cell network. Depending on the cell radio
network type, these records contain different information.

The classification of radio types is based on the `Android TelephonyManager
constants <http://developer.android.com/reference/android/telephony/TelephonyManager.html>`_.
A similar classification exists for Firefox OS devices with the
`MozMobileConnectionInfo API <https://developer.mozilla.org/en-US/docs/Web/API/MozMobileConnectionInfo.type>`_.

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
    According to `TS 24.008 10.5.3 <http://www.etsi.org/deliver/etsi_ts/124000_124099/124008/12.07.00_60/ts_124008v120700p.pdf#page=431>`_ both 0 and 65534 are reserved
    values indicating a deleted state.

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
        "radio": "umts",
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
    According to `TS 24.008 10.5.3 <http://www.etsi.org/deliver/etsi_ts/124000_124099/124008/12.07.00_60/ts_124008v120700p.pdf#page=431>`_ both 0 and 65534 are reserved
    values indicating a deleted state.

cid **(required)**
    The cell id. An integer in the range of 1 to 268435455.

psc
    The primary scrambling code as an integer in the range of 0 to 511
    (optional).

signal
    The received signal code power (RSCP) in dBm, typically in the range of
    -25 to -121 (optional).

asu
    The arbitrary strength unit. An integer in the range of -5 to 91 (optional).
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
    According to `TS 24.301 9.9.3.32 <http://www.etsi.org/deliver/etsi_ts/124300_124399/124301/12.06.00_60/ts_124301v120600p.pdf#page=286>`_ both 0 and 65534 are reserved
    values indicating a deleted state.

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
