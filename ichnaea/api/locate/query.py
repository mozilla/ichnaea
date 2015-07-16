"""
Code representing a location query.
"""

import six

from ichnaea.api.locate.constants import MIN_WIFIS_IN_QUERY
from ichnaea.api.locate.schema import (
    CellAreaLookup,
    CellLookup,
    WifiLookup,
)

if six.PY2:  # pragma: no cover
    from ipaddr import IPAddress as ip_address  # NOQA
else:  # pragma: no cover
    from ipaddress import ip_address


class Query(object):

    def __init__(self, fallbacks=None, geoip=None, cell=None, wifi=None):
        """
        A class representing a concrete location query.

        :param fallbacks: A dictionary of fallback options.
        :type fallbacks: dict

        :param geoip: An IP address, e.g. 127.0.0.1.
        :type geoip: str

        :param cell: A list of cell query dicts.
        :type cell: list

        :param wifi: A list of wifi query dicts.
        :type wifi: list
        """
        self.fallbacks = fallbacks
        self.geoip = geoip
        self.cell = cell
        self.wifi = wifi
        self.fallbacks = fallbacks

    @property
    def geoip(self):
        """The validated geoip."""
        return self._geoip

    @geoip.setter
    def geoip(self, value):
        if not value:
            value = None
        try:
            valid = str(ip_address(value))
        except ValueError:
            valid = None
        self._geoip = valid

    @property
    def cell(self):
        """
        The validated list of
        :class:`~ichnaea.api.locate.schema.CellLookup` instances.

        If the same cell network is supplied multiple times, this chooses only
        the best entry for each unique network.
        """
        return self._cell

    @property
    def cell_area(self):
        """
        The validated list of
        :class:`~ichnaea.api.locate.schema.CellAreaLookup` instances.

        If the same cell area is supplied multiple times, this chooses only
        the best entry for each unique area.
        """
        return self._cell_area

    @cell.setter
    def cell(self, values):
        if not values:
            values = []
        values = list(values)
        self._cell_unvalidated = values

        filtered_areas = []
        filtered_cells = []
        for value in values:
            valid_area = CellAreaLookup.create(**value)
            if valid_area:
                filtered_areas.append(valid_area)
            valid_cell = CellLookup.create(**value)
            if valid_cell:
                filtered_cells.append(valid_cell)
        self._cell_area = filtered_areas
        self._cell = filtered_cells

    @property
    def wifi(self):
        """
        The validated list of
        :class:`~ichnaea.api.locate.schema.WifiLookup` instances.

        If the same Wifi network is supplied multiple times, this chooses only
        the best entry for each unique network.

        If fewer than :data:`~ichnaea.api.locate.constants.MIN_WIFIS_IN_QUERY`
        unique valid Wifi networks are found, returns an empty list.
        """
        return self._wifi

    @wifi.setter
    def wifi(self, values):
        if not values:
            values = []
        values = list(values)
        self._wifi_unvalidated = values

        filtered = []
        for value in values:
            valid = WifiLookup.create(**value)
            if valid:
                filtered.append(valid)
        if len(filtered) < MIN_WIFIS_IN_QUERY:
            filtered = []
        self._wifi = filtered

    @property
    def fallbacks(self):
        return self._fallbacks

    @fallbacks.setter
    def fallbacks(self, values):
        if not values:
            values = {}
        self._fallbacks = values
