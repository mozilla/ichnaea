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

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

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

    @property
    def fallbacks(self):
        """
        A dictionary of fallback options.
        """
        return self._fallbacks

    @fallbacks.setter
    def fallbacks(self, values):
        if not values:
            values = {}
        self._fallbacks = values

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

        filtered_areas = OrderedDict()
        filtered_cells = OrderedDict()
        for value in values:
            valid_area = CellAreaLookup.create(**value)
            if valid_area:
                existing = filtered_areas.get(valid_area.hashkey())
                if existing is not None and existing.better(valid_area):
                    pass
                else:
                    filtered_areas[valid_area.hashkey()] = valid_area
            valid_cell = CellLookup.create(**value)
            if valid_cell:
                existing = filtered_cells.get(valid_cell.hashkey())
                if existing is not None and existing.better(valid_cell):
                    pass
                else:
                    filtered_cells[valid_cell.hashkey()] = valid_cell
        self._cell_area = filtered_areas.values()
        self._cell = filtered_cells.values()

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

        filtered = OrderedDict()
        for value in values:
            valid_wifi = WifiLookup.create(**value)
            if valid_wifi:
                existing = filtered.get(valid_wifi.hashkey())
                if existing is not None and existing.better(valid_wifi):
                    pass
                else:
                    filtered[valid_wifi.hashkey()] = valid_wifi

        if len(filtered) < MIN_WIFIS_IN_QUERY:
            filtered = {}
        self._wifi = filtered.values()
