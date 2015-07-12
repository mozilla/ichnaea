"""
Code representing a location query.
"""

import ipaddr

from ichnaea.api.locate.constants import MIN_WIFIS_IN_QUERY
from ichnaea.api.locate.schema import (
    CellAreaLookup,
    CellLookup,
    WifiLookup,
)


class Query(object):

    def __init__(self, geoip=None, cell=None, wifi=None, fallbacks=None):
        """
        A class representing a concrete location query.

        :param geoip: An IP address, e.g. 127.0.0.1.
        :type geoip: str

        :param cell: A list of cell query dicts.
        :type cell: list

        :param wifi: A list of wifi query dicts.
        :type wifi: list

        :param fallbacks: A dictionary of fallback options.
        :type fallbacks: dict
        """
        self.geoip = geoip
        self.cell = cell
        self.wifi = wifi
        self.fallbacks = fallbacks

    @property
    def geoip(self):
        return self._geoip

    @geoip.setter
    def geoip(self, value):
        if not value:
            value = None
        try:
            valid = str(ipaddr.IPAddress(value))
        except ValueError:
            valid = None
        self._geoip = valid

    @property
    def cell(self):
        return self._cell

    @property
    def cell_area(self):
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
            valid_area = CellAreaLookup.validate(value)
            if valid_area:
                filtered_areas.append(valid_area)
            valid_cell = CellLookup.validate(value)
            if valid_cell:
                filtered_cells.append(valid_cell)
        self._cell_area = filtered_areas
        self._cell = filtered_cells

    @property
    def wifi(self):
        return self._wifi

    @wifi.setter
    def wifi(self, values):
        if not values:
            values = []
        values = list(values)
        self._wifi_unvalidated = values

        filtered = []
        for value in values:
            valid = WifiLookup.validate(value)
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
