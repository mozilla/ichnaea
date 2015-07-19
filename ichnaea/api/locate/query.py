"""
Code representing a location query.
"""

import six

from ichnaea.api.locate.constants import MIN_WIFIS_IN_QUERY
from ichnaea.api.locate.schema import (
    CellAreaLookup,
    CellLookup,
    FallbackLookup,
    WifiLookup,
)

try:
    from collections import OrderedDict
except ImportError:  # pragma: no cover
    from ordereddict import OrderedDict

if six.PY2:  # pragma: no cover
    from ipaddr import IPAddress as ip_address  # NOQA
else:  # pragma: no cover
    from ipaddress import ip_address

METRIC_MAPPING = {
    0: 'none',
    1: 'one',
    2: 'many',
}


class Query(object):

    def __init__(self, fallback=None, geoip=None, cell=None, wifi=None,
                 api_key=None, api_name=None, api_type=None,
                 session=None, stats_client=None):
        """
        A class representing a concrete location query.

        :param fallback: A dictionary of fallback options.
        :type fallback: dict

        :param geoip: An IP address, e.g. 127.0.0.1.
        :type geoip: str

        :param cell: A list of cell query dicts.
        :type cell: list

        :param wifi: A list of wifi query dicts.
        :type wifi: list

        :param api_key: An ApiKey instance for the current query.
        :type api_key: :class:`ichnaea.models.api.ApiKey`

        :param api_name: Name of the API, used as a stats prefix
            (for example 'geolocate')
        :type api_name: str

        :param api_type: The type of query API, for example `locate`.
        :type api_type: str

        :param session: An open database session.

        :param stats_client: A stats client.
        :type stats_client: :class:`~ichnaea.log.PingableStatsClient`
        """
        self.fallback = fallback
        self.geoip = geoip
        self.cell = cell
        self.wifi = wifi
        self.api_key = api_key
        self.api_name = api_name
        self.api_type = api_type
        self.session = session
        self.stats_client = stats_client

    @property
    def fallback(self):
        """
        A validated
        :class:`~ichnaea.api.locate.schema.FallbackLookup` instance.
        """
        return self._fallback

    @fallback.setter
    def fallback(self, values):
        if not values:
            values = {}
        valid = FallbackLookup.create(**values)
        if valid is None:  # pragma: no cover
            valid = FallbackLookup.create()
        self._fallback = valid

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
        self._cell_area = list(filtered_areas.values())
        self._cell = list(filtered_cells.values())

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
        self._wifi = list(filtered.values())

    def internal_query(self):
        """Returns a dictionary of this query in our internal format."""
        result = {}
        if self.cell:
            result['cell'] = []
            for cell in self.cell:
                cell_data = {}
                for field in cell._fields:
                    cell_data[field] = getattr(cell, field)
                result['cell'].append(cell_data)
        if self.wifi:
            result['wifi'] = []
            for wifi in self.wifi:
                wifi_data = {}
                for field in wifi._fields:
                    wifi_data[field] = getattr(wifi, field)
                result['wifi'].append(wifi_data)
        if self.fallback:
            fallback_data = {}
            for field in self.fallback._fields:
                fallback_data[field] = getattr(self.fallback, field)
            result['fallbacks'] = fallback_data
        return result

    def emit_query_stats(self):
        """Emit stats about the data contained in this query."""
        if not self.api_key.log or not self.api_type:
            return

        cells = len(self.cell)
        wifis = len(self._wifi_unvalidated)

        if self.geoip:
            country = ''
        else:
            country = 'none'

        prefix = '{api_type}.query.{key}.'.format(
            api_type=self.api_type,
            key=self.api_key.name)
        all_prefix = prefix + 'all.'
        country_prefix = prefix + country + '.'

        if self.geoip and not (cells or wifis):
            self.stats_client.incr(all_prefix + 'geoip.only')
            if country:  # pragma: no cover
                self.stats_client.incr(country_prefix + 'geoip.only')
        else:
            for name, length in (('cell', cells), ('wifi', wifis)):
                num = METRIC_MAPPING[min(length, 2)]
                metric = '{name}.{num}'.format(name=name, num=num)
                self.stats_client.incr(all_prefix + metric)
                if country:
                    self.stats_client.incr(country_prefix + metric)

    def stat_count(self, stat):
        """Emit an api_name specific stat counter."""
        self.stats_client.incr('{api}.{stat}'.format(
            api=self.api_name, stat=stat))

    def stat_timer(self, stat):
        """
        Return a context manager to capture an api_name specific stat timer.
        """
        return self.stats_client.timer('{api}.{stat}'.format(
            api=self.api_name, stat=stat))
