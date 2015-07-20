"""Code representing a query."""

import six

from ichnaea.api.locate.constants import (
    DataAccuracy,
    MIN_WIFIS_IN_QUERY,
)
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

    _country = None
    _fallback = None
    _geoip = None
    _ip = None

    def __init__(self, fallback=None, ip=None, cell=None, wifi=None,
                 api_key=None, api_name=None, api_type=None,
                 session=None, geoip_db=None, stats_client=None):
        """
        A class representing a concrete query.

        :param fallback: A dictionary of fallback options.
        :type fallback: dict

        :param ip: An IP address, e.g. 127.0.0.1.
        :type ip: str

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

        :param geoip_db: A geoip database.
        :type geoip_db: :class:`~ichnaea.geoip.GeoIPWrapper`

        :param stats_client: A stats client.
        :type stats_client: :class:`~ichnaea.log.PingableStatsClient`
        """
        self.geoip_db = geoip_db
        self.session = session
        self.stats_client = stats_client

        self.fallback = fallback
        self.ip = ip
        self.cell = cell
        self.wifi = wifi
        self.api_key = api_key
        self.api_name = api_name
        self.api_type = api_type

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
    def country(self):
        """
        The two letter country code of origin for this query.

        Can return None, if no country could be determined.
        """
        return self._country

    @property
    def geoip(self):
        """
        A GeoIP database entry for the originating IP address.

        Can return None if no database match could be found.
        """
        return self._geoip

    @property
    def ip(self):
        """The validated IP address."""
        return self._ip

    @ip.setter
    def ip(self, value):
        if not value:
            value = None
        try:
            valid = str(ip_address(value))
        except ValueError:
            valid = None
        self._ip = valid
        if valid:
            country = None
            geoip = None
            if self.geoip_db:
                geoip = self.geoip_db.geoip_lookup(valid)
                if geoip:
                    country = geoip.get('country_code')
                    if country:
                        country = country.upper()
            self._geoip = geoip
            self._country = country

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

    @property
    def expected_accuracy(self):
        if self.wifi:
            return DataAccuracy.high
        if self.cell:
            return DataAccuracy.medium
        return DataAccuracy.low

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

    def emit_country_stat(self, pre, post):
        """Emit a all/country stats pair."""
        self.stats_client.incr(pre + 'all' + post)
        country = self.country
        if not country:
            country = 'none'
            # TODO don't emit actual country based stats yet
            self.stats_client.incr(pre + country + post)

    def emit_query_stats(self):
        """Emit stats about the data contained in this query."""
        if not self.api_key.log or not self.api_type:
            return

        cells = len(self.cell)
        wifis = len(self._wifi_unvalidated)

        prefix = '{api_type}.query.{key}.'.format(
            api_type=self.api_type,
            key=self.api_key.name)

        if self.ip and not (cells or wifis):
            self.emit_country_stat(prefix, '.geoip.only')
        else:
            for name, length in (('cell', cells), ('wifi', wifis)):
                num = METRIC_MAPPING[min(length, 2)]
                metric = '.{name}.{num}'.format(name=name, num=num)
                self.emit_country_stat(prefix, metric)

    def emit_provider_stats(self, provider, result):
        """Emit stats about a specific provider."""

        pre = '{api_type}.source.{key}.'.format(
            api_type=self.api_type,
            key=self.api_key.name)

        post = '.{provider}.{result}'.format(
            provider=provider, result=result)

        self.emit_country_stat(pre, post)

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
