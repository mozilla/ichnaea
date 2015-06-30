.. _import_export:

====================
Data Import / Export
====================

Ichnaea supports automatic, periodic CSV (comma separated values) export
of aggregate cell data (position estimates) and periodic import of
the same type of data from the OpenCellID project.

The data exchange format was created in collaboration with the
`OpenCellID <http://opencellid.org>`_ project.

Records should be written one record to a line, with `\\n` (0x0A) as line
separator.

A value should be written as an empty field -- two adjacent commas, for
example -- rather than being omitted.

The first five fields (radio to cell) jointly identify a unique logical cell
network. The remaining fields contain information about this network.

The data format does not specify the means and exact algorithms by which the
position estimate or range calculation was done. The algorithms might be
unique and changing for each source of the data, though both MLS and
OpenCellID currently use similar and comparable techniques.

The fields in the CSV file are as follows:

Cell Fields
-----------

``radio``

    Network type. One of the strings `GSM`, `UMTS`, `LTE` or `CDMA`.

``mcc``

    Mobile Country Code. An integer, for example `505`, the code for Australia.

``net``

    For GSM, UMTS and LTE networks, this is the Mobile Network Code (MNC). For
    CDMA networks, this is the System Identification number (SID). An integer,
    for example `4`, the MNC used by Vodaphone in the Netherlands.

``area``

    For GSM and UMTS networks, this is the Location Area Code (LAC). For LTE
    networks, this is the Tracking Area Code (TAC). For CDMA networks, this is
    the Network Idenfitication number (NID). An integer, for example `2035`.

``cell``

    For GSM and LTE networks, this is the Cell ID (CID). For UMTS networks
    this is the UTRAN Cell ID / LCID, which is the concatenation of 2 or 4
    bytes of Radio Network Controller (RNC) code and 4 bytes of Cell ID.
    For CDMA networks this is the Base station Identifier number (BID).
    An integer, for example `32345`

``unit``

    For UMTS networks, this is the Primary Scrambling Code (PSC). For LTE
    networks, this is the Physical Cell ID (PCI). For GSM and CDMA networks,
    this is empty. An integer, for example `312`.

``lon``

    Longitude in degrees between -180.0 and 180.0 using the WSG 84 reference
    system. A floating point number, for example `52.3456789`.

``lat``

    Latitude in degrees between -90.0 and 90.0 using the WSG 84 reference
    system. A floating point number, for example `-10.034`.

``range``

    Estimate of radio range, in meters. This is an estimate on how large each
    cell area is, as a radius around the estimated position and is based on
    the observations or a knowledgeable source. An integer, for example `2500`.

``samples``

    Total number of observations used to calculate the estimated position,
    range and averageSignal. An integer, for example `1200`.

``changeable``

    Whether or not this cell is a position estimate based on radio
    observations, and therefore subject to change in the future, or is an
    exact location entered from a knowledgeable source. A boolean value,
    encoded as either `1` (for "changeable") or `0` (for "exact").

``created``

    Timestamp of the time when this record was first created. An integer,
    counting seconds since the UTC Unix Epoch of 1970-01-01T00:00:00Z.
    For example, `1406204196`, which is the timestamp for 2014-07-24T12:16:36Z.

``updated``

    Timestamp of the time when this record was most recently modified. An
    integer, counting seconds since the UTC Unix Epoch of 1970-01-01T00:00:00Z.
    For example, `1406204196`, which is the timestamp for 2014-07-24T12:16:36Z.

``averageSignal``

    Average signal strength from all observations for the cell network.
    An integer value, in dBm. For example, `-72`.

    This field is only used by the OpenCellID project and historically has
    been used as a hint towards the quality of the position estimate.
