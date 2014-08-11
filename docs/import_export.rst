.. _import_export:

==================
Data import/export
==================

Ichaea supports automatic, periodic CSV (comma separated values) import/export of aggregate station
data (cell and wifi position estimates).

Records should be written one record to a line, with `\\n` (0x0A) as line separator.

A value should be written as an empty field -- two adjacent commas, for example -- rather than not omitted.

The fields in the CSV file are as follows:

Cell Fields
-----------

``radio``

    Network type. One of the strings `GSM`, `UMTS`, `LTE`, `CDMA`

``mcc``

    Mobile Country Code. An integer, for example `505`, the code for Australia.

``net``

    For GSM, UMTS and LTE networks, this is the Mobile Network Code (MNC). For CDMA networks, this
    is the System IDentification number (SID). An integer, for example `04`, the MNC used by
    Vodaphone in the Netherlands.

``area``

    For GSM and UMTS networks, this is the Location Area Code (LAC). For LTE networks, this is the
    Tracking Area Code (TAC).  For CDMA networks, this is the Network IDenfitication number (NID).
    An integer, for example `2035`.

``cell``

    For GSM and LTE networks, this is the Cell ID (CID). For UMTS networks this is the UTRAN Cell ID
    / LCID, which is the concatenation of 2 bytes of Radio Network Controller (RNC) code and 4 bytes
    of Cell ID. For CDMA networks this is the Billing IDentification number (BID). An integer,
    for example `32345`

``unit``

    For UMTS networks, this is the Primary Scrambling Code (PSC). For LTE networks, this is the
    Physical Cell ID (PCI). For GSM and CDMA networks, this is empty. An integer, for example `312`.

``lon``

    Longitude in degrees between -180 and 180. The prime meridian is 0 degrees, with positive
    numbers to the east and negative numbers to the west. A floating point number, for example
    `52.3456789`.

``lat``

    Latitude in degrees between -90 and 90. The equator is 0 degrees, with positive numbers to the
    north the negative numbers to the south. A floating point number, for example `-10.03456`.

``range``

    Estimate of radio range, in meters. An integer, for example `2500`.

``samples``

    Total number of measurements used to calculate this aggregate value. An integer, fo rexample
    `1234`.

``changeable``

    Whether or not this cell is a position estimate from radio measurements, and therefore subject
    to change in the future, or is an exact location entered from a knowledgable source. A boolean
    value, encoded as either `1` (for "changeable") or `0` (for "exact").

``created``

    Timestamp of the time when this record was first created. An integer, counting seconds since
    the UTC Unix Epoch of 1970-01-01T00:00:00Z. For example, `1406204196`, which is the timestamp for
    2014-07-24T12:16:36Z.

``updated``

    Timestamp of the time when this record was most recently modified. An integer, counting seconds
    since the UTC Unix Epoch of 1970-01-01T00:00:00Z. For example, `1406204196`, which is the
    timestamp for 2014-07-24T12:16:36Z.

``averageSignal``

    Average signal strength for the cell. An integer value, in Arbitrary Strength Units (ASU),
    which are interpreted in different ways depending on the cell network.
