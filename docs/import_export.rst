.. _import_export:

======================
Data import and export
======================

Data export
===========

Ichnaea supports automatic, periodic CSV (comma separated values) export of
aggregate cell data (position estimates). Mozilla's exports are available at
`<https://location.services.mozilla.com/downloads>`_

The data exchange format was created in collaboration with the
:term:`OpenCellID` project.

Records should be written one record to a line with CRLF (0x0D 0x0A)
as line separator.

A value should be written as an empty field—two adjacent commas, for
example—rather than being omitted.

The first five fields (radio to cell) jointly identify a unique logical cell
network. The remaining fields contain information about this network.

The data format does not specify the means and exact algorithms by which the
position estimate or range calculation was done. The algorithms might be
unique and changing for each source of the data, though both Ichnaea and
:term:`OpenCellID` currently use similar and comparable techniques.


Cell Fields
-----------

The fields in the CSV file are as follows:


radio
    Network type. One of the strings ``GSM``, ``UMTS`` (for WCMDA networks), or
    ``LTE``.

mcc
    Mobile Country Code. This is an integer.

    For example, ``505`` is the code for Australia.

net
    For GSM, UMTS, and LTE networks, this is the mobile network code (MNC).
    This is an integer.

    For example, ``4`` is the MNC used by Vodaphone in the Netherlands.

area
    For GSM and UMTS networks, this is the location area code (LAC). For LTE
    networks, this is the tracking area code (TAC). This is an integer.

    For example, ``2035``.

cell
    For GSM and LTE networks, this is the cell id or cell identity (CID).
    For UMTS networks this is the UTRAN cell id, which is the concatenation
    of 2 bytes of radio network controller (RNC) code and 2 bytes of cell id.
    This is an integer.

    For example, ``32345``.

unit
    For UMTS networks, this is the primary scrambling code (PSC). For LTE
    networks, this is the physical cell id (PCI). For GSM networks, this is
    empty. This is an integer.

    For example, ``312``.

lon
    Longitude in degrees between -180.0 and 180.0 using the WSG 84 reference
    system. This is a floating point number.

    For example, ``52.3456789``.

lat
    Latitude in degrees between -90.0 and 90.0 using the WSG 84 reference
    system. This is a floating point number.

    For example, ``-10.034``.

range
    Estimate of radio range, in meters. This is an estimate on how large each
    cell area is, as a radius around the estimated position and is based on
    the :term:`observations` or a knowledgeable source. This is an integer.

    For example, ``2500``.

samples
    Total number of :term:`observations` used to calculate the estimated
    position, range and averageSignal. This is an integer.

    For example, ``1200``.

changeable
    Whether or not this cell is a position estimate based on
    :term:`observations` subject to change in the future or an exact location
    entered from a knowledgeable source. This is a boolean value, encoded as
    either ``1`` (for "changeable") or ``0`` (for "exact").

created
    Timestamp of the time when this record was first created. This is an
    integer counting seconds since the UTC Unix Epoch of 1970-01-01T00:00:00Z.

    For example, ``1406204196`` which is the timestamp for
    2014-07-24T12:16:36Z.

updated
    Timestamp of the time when this record was most recently modified. This is
    an integer, counting seconds since the UTC Unix Epoch of
    1970-01-01T00:00:00Z.

    For example, ``1406204196``, which is the timestamp for
    2014-07-24T12:16:36Z.

averageSignal
    Average signal strength from all observations for the cell network. This
    is an integer value, in dBm.

    For example, ``-72``.

    This field is only used by the :term:`OpenCellID` project and has been used
    historically as a hint towards the quality of the position estimate.


Data import
===========

Aggregate cell data can be imported into an Ichnaea instance.  For the
development environment:

1. Download a Differental Cell Export from `Mozilla's Download page
   <https://location.services.mozilla.com/downloads>`_.  Do not extract it, but
   keep it in the compressed ``.csv.gz`` format, in the root of the repository.

2. In a shell in the app container, import the data::

    $ make shell
    # Replace with the filename of the downloaded export file
    app@blahblahblah:/app$ ichnaea/scripts/load_cell_data.py MLS-diff-cell-export-YYYY-MM-DDTHH0000.csv.gz

This will import the cell data, then queue tasks to aggregrate cell areas and
region statistics. It should take about a minute to process an 300kB export of
10,000 stations.

Importing a Full Cell Export is not recommended. This will fail due to
unexpected data, and the development environment may require undocumented
changes for the larger resource requirements of a full cell export.
